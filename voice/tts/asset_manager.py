"""Prepared WAV recordings and a bounded cache for synthesized audio."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

from core.app_paths import APP_DATA_DIR
from .models import VoiceProfile

logger = logging.getLogger("jarvis.tts.assets")
_CACHE_KEY_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class AudioAssetManager:
    """Store prepared audio separately from disposable generated-audio cache.

    Format v1 deliberately accepts only uncompressed 16-bit PCM WAV, mono or stereo.
    Other formats should be converted before import, avoiding a new codec dependency.
    """

    def __init__(self, root_dir: str | Path | None = None, max_cache_bytes: int = 256 * 1024 * 1024) -> None:
        self.root_dir = Path(root_dir) if root_dir is not None else APP_DATA_DIR / "tts" / "assets"
        self.prepared_dir = self.root_dir / "prepared"
        self.cache_dir = self.root_dir / "cache"
        self.manifest_path = self.root_dir / "prepared_manifest.json"
        self.max_cache_bytes = max(1024, int(max_cache_bytes))
        self._lock = threading.RLock()
        self._manifest = self._read_manifest()

    @staticmethod
    def cache_key(text: str, profile: VoiceProfile | dict[str, Any] | str, *, engine_id: str | None = None,
                  model_id: str | None = None, settings: dict[str, Any] | None = None) -> str:
        if isinstance(profile, VoiceProfile):
            voice_id = profile.voice_id
            engine_id = engine_id or profile.engine_id
            model_id = model_id or profile.model_id
            merged_settings = {**profile.settings, **(settings or {})}
        elif isinstance(profile, dict):
            voice_id = str(profile.get("voice_id", profile.get("id", "")))
            engine_id = engine_id or str(profile.get("engine_id", ""))
            model_id = model_id or str(profile.get("model_id", ""))
            base_settings = profile.get("settings", {})
            merged_settings = {**(base_settings if isinstance(base_settings, dict) else {}), **(settings or {})}
        else:
            voice_id = str(profile)
            merged_settings = dict(settings or {})
        if not voice_id:
            raise ValueError("A voice_id is required to build an audio cache key")
        payload = {"text": " ".join(str(text or "").split()), "voice_id": voice_id,
                   "engine_id": engine_id or "", "model_id": model_id or "", "settings": merged_settings}
        try:
            canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Voice settings must be JSON-serializable") from exc
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _text_key(text: str) -> str:
        normalized = " ".join(str(text or "").split()).casefold()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def find_prepared_audio_for_text(self, voice_id: str, text: str) -> Path | None:
        """Find the prepared recording for an exact normalized utterance."""
        text_key = self._text_key(text)
        with self._lock:
            for entry in self._manifest.values():
                if not isinstance(entry, dict):
                    continue
                if entry.get("voice_id") != voice_id or entry.get("text_key") != text_key:
                    continue
                relative = entry.get("path")
                if not isinstance(relative, str):
                    continue
                path = (self.root_dir / relative).resolve()
                if path.parent == self.prepared_dir.resolve() and path.is_file():
                    return path
        return None

    def list_prepared_audio(self, voice_id: str | None = None) -> list[dict[str, Any]]:
        """Return safe metadata for the UI; never expose paths outside the managed folder."""
        results = []
        with self._lock:
            for entry in self._manifest.values():
                if not isinstance(entry, dict):
                    continue
                if voice_id is not None and entry.get("voice_id") != voice_id:
                    continue
                relative = entry.get("path")
                if not isinstance(relative, str):
                    continue
                path = (self.root_dir / relative).resolve()
                if path.parent != self.prepared_dir.resolve() or not path.is_file():
                    continue
                results.append({
                    "voice_id": str(entry.get("voice_id", "")),
                    "response_key": str(entry.get("response_key", "")),
                    "text_preview": str(entry.get("text_preview", "")),
                    "path": str(path),
                    "size_bytes": path.stat().st_size,
                    "updated_at": entry.get("updated_at"),
                })
        return sorted(results, key=lambda item: (item["voice_id"], item["response_key"]))

    def remove_prepared_audio(self, voice_id: str, response_key: str) -> bool:
        asset_id = self._prepared_id(voice_id, response_key)
        with self._lock:
            entry = self._manifest.get(asset_id)
            if not isinstance(entry, dict) or entry.get("voice_id") != voice_id or entry.get("response_key") != response_key:
                return False
            relative = entry.get("path")
            path = (self.root_dir / relative).resolve() if isinstance(relative, str) else None
            if path is not None and path.parent == self.prepared_dir.resolve():
                path.unlink(missing_ok=True)
            del self._manifest[asset_id]
            self._write_manifest()
            return True

    def find_prepared_audio(self, voice_id: str, response_key: str) -> Path | None:
        asset_id = self._prepared_id(voice_id, response_key)
        with self._lock:
            entry = self._manifest.get(asset_id)
            relative = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(relative, str):
                return None
            path = (self.root_dir / relative).resolve()
            if path.parent != self.prepared_dir.resolve() or not path.is_file():
                return None
            return path

    def register_prepared_file(
        self, voice_id: str, response_key: str, source_path: str | Path, *, text: str | None = None
    ) -> Path:
        self._validate_logical_key(voice_id, "voice_id")
        self._validate_logical_key(response_key, "response_key")
        source = Path(source_path)
        self._validate_wav(source)
        target = self.prepared_dir / f"{self._prepared_id(voice_id, response_key)}.wav"
        with self._lock:
            self.prepared_dir.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(".wav.tmp")
            try:
                shutil.copyfile(source, temporary)
                self._validate_wav(temporary)
                os.replace(temporary, target)
            finally:
                temporary.unlink(missing_ok=True)
            self._manifest[self._prepared_id(voice_id, response_key)] = {
                "voice_id": voice_id, "response_key": response_key,
                "path": f"prepared/{target.name}", "updated_at": time.time(),
                "text_key": self._text_key(text) if text and text.strip() else None,
                "text_preview": " ".join(text.split())[:140] if text and text.strip() else "",
            }
            self._write_manifest()
        return target

    def save_prepared_audio(
        self, voice_id: str, response_key: str, audio: np.ndarray, sample_rate: int, *, text: str | None = None
    ) -> Path:
        self._validate_logical_key(voice_id, "voice_id")
        self._validate_logical_key(response_key, "response_key")
        target = self.prepared_dir / f"{self._prepared_id(voice_id, response_key)}.wav"
        with self._lock:
            self.prepared_dir.mkdir(parents=True, exist_ok=True)
            self._write_wav_atomic(target, audio, sample_rate)
            self._manifest[self._prepared_id(voice_id, response_key)] = {
                "voice_id": voice_id, "response_key": response_key,
                "path": f"prepared/{target.name}", "updated_at": time.time(),
                "text_key": self._text_key(text) if text and text.strip() else None,
                "text_preview": " ".join(text.split())[:140] if text and text.strip() else "",
            }
            self._write_manifest()
        return target

    def find_cached_audio(self, cache_key: str) -> Path | None:
        self._validate_cache_key(cache_key)
        path = self.cache_dir / f"{cache_key}.wav"
        if not path.is_file():
            return None
        try:
            os.utime(path, None)
        except OSError:
            pass
        return path

    def save_cached_audio(self, cache_key: str, audio: np.ndarray, sample_rate: int) -> Path | None:
        self._validate_cache_key(cache_key)
        with self._lock:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path = self.cache_dir / f"{cache_key}.wav"
            self._write_wav_atomic(path, audio, sample_rate)
            if path.stat().st_size > self.max_cache_bytes:
                path.unlink(missing_ok=True)
                logger.debug("tts_cache_skip_oversize key=%s", cache_key)
                return None
            self.prune_cache()
            return path if path.is_file() else None

    def load_audio(self, path: str | Path) -> tuple[np.ndarray, int]:
        source = Path(path)
        self._validate_wav(source)
        with wave.open(str(source), "rb") as wav_file:
            channels, sample_rate = wav_file.getnchannels(), wav_file.getframerate()
            frames = wav_file.readframes(wav_file.getnframes())
        audio = np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768.0
        if channels > 1:
            audio = audio.reshape(-1, channels)
        return audio.copy(), int(sample_rate)

    def prune_cache(self, max_bytes: int | None = None) -> int:
        limit = self.max_cache_bytes if max_bytes is None else max(0, int(max_bytes))
        with self._lock:
            files = [path for path in self.cache_dir.glob("*.wav") if path.is_file()] if self.cache_dir.exists() else []
            total = sum(path.stat().st_size for path in files)
            removed = 0
            for path in sorted(files, key=lambda item: item.stat().st_mtime):
                if total <= limit:
                    break
                try:
                    size = path.stat().st_size
                    path.unlink()
                    total -= size
                    removed += 1
                except OSError:
                    logger.warning("tts_cache_eviction_failed path=%s", path, exc_info=True)
            return removed

    def clear_cache(self) -> int:
        with self._lock:
            files = list(self.cache_dir.glob("*.wav")) if self.cache_dir.exists() else []
            removed = 0
            for path in files:
                try:
                    path.unlink()
                    removed += 1
                except OSError:
                    logger.warning("tts_cache_clear_failed path=%s", path, exc_info=True)
            return removed

    @staticmethod
    def _validate_logical_key(value: str, label: str) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            raise ValueError(f"{label} must contain 1 to 200 characters")

    @staticmethod
    def _prepared_id(voice_id: str, response_key: str) -> str:
        return hashlib.sha256(f"{voice_id}\0{response_key}".encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_cache_key(cache_key: str) -> None:
        if not isinstance(cache_key, str) or not _CACHE_KEY_PATTERN.fullmatch(cache_key):
            raise ValueError("cache_key must be a lowercase SHA-256 hex digest")

    @staticmethod
    def _validate_wav(path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(path)
        try:
            with wave.open(str(path), "rb") as source:
                if source.getcomptype() != "NONE" or source.getsampwidth() != 2:
                    raise ValueError("Audio assets must be uncompressed 16-bit PCM WAV files")
                if source.getnchannels() not in (1, 2) or source.getframerate() <= 0:
                    raise ValueError("Audio assets must be mono/stereo WAV with a positive sample rate")
        except (wave.Error, EOFError) as exc:
            raise ValueError(f"Invalid PCM WAV file: {path}") from exc

    @staticmethod
    def _write_wav_atomic(path: Path, audio: np.ndarray, sample_rate: int) -> None:
        if int(sample_rate) <= 0:
            raise ValueError("sample_rate must be positive")
        values = np.asarray(audio, dtype=np.float32)
        if values.ndim not in (1, 2) or (values.ndim == 2 and values.shape[1] not in (1, 2)):
            raise ValueError("Audio must be mono or stereo PCM data")
        if values.size == 0:
            raise ValueError("Audio must not be empty")
        values = np.nan_to_num(values, nan=0.0, posinf=1.0, neginf=-1.0)
        pcm = (np.clip(values, -1.0, 1.0) * 32767.0).astype("<i2")
        channels = 1 if values.ndim == 1 else int(values.shape[1])
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            with wave.open(str(temporary), "wb") as output:
                output.setnchannels(channels)
                output.setsampwidth(2)
                output.setframerate(int(sample_rate))
                output.writeframes(pcm.tobytes())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_manifest(self) -> dict[str, dict[str, Any]]:
        try:
            data = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            prepared = data.get("prepared", {}) if isinstance(data, dict) else {}
            return prepared if isinstance(prepared, dict) else {}
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("tts_prepared_manifest_load_failed path=%s error=%s", self.manifest_path, exc)
            return {}

    def _write_manifest(self) -> None:
        self.root_dir.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(self.manifest_path.suffix + ".tmp")
        temporary.write_text(json.dumps({"version": 1, "prepared": self._manifest}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.manifest_path)
