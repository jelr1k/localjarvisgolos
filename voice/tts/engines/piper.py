from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

import numpy as np
import requests

from core.app_paths import APP_DATA_DIR
from ..errors import TTSConfigurationError, TTSError, TTSVoiceNotInstalledError
from ..text import prepare_speech_text

logger = logging.getLogger("jarvis.tts")

DEFAULT_TTS_VOICE = "ru_RU-dmitri-medium"
DEFAULT_TTS_SPEED = 1.0
DEFAULT_TTS_VOLUME = 0.85
MAX_VOICE_FILE_BYTES = 256 * 1024 * 1024

# Explicit allow-list keeps model downloads restricted to known HTTPS assets.
SUPPORTED_TTS_VOICES = {
    "ru_RU-dmitri-medium": ("ru/ru_RU/dmitri/medium", "ru_RU-dmitri-medium", "Дмитрий · русский · medium"),
    "ru_RU-irina-medium": ("ru/ru_RU/irina/medium", "ru_RU-irina-medium", "Ирина · русский · medium"),
    "ru_RU-ruslan-medium": ("ru/ru_RU/ruslan/medium", "ru_RU-ruslan-medium", "Руслан · русский · medium"),
}

class PiperTTSBackend:
    """Lazy local Piper backend. Voice files live in AppData, not in the repository."""

    engine_id = "piper"

    VOICE_ROOT = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

    def __init__(
        self,
        model_dir: str | Path | None = None,
        voice_name: str = DEFAULT_TTS_VOICE,
        speed: float = DEFAULT_TTS_SPEED,
        volume: float = DEFAULT_TTS_VOLUME,
    ):
        self.model_dir = Path(model_dir) if model_dir is not None else APP_DATA_DIR / "tts" / "voices"
        self.voice_name = DEFAULT_TTS_VOICE
        self.speed = DEFAULT_TTS_SPEED
        self.volume = DEFAULT_TTS_VOLUME
        self._voice = None
        self._loaded_voice_name: str | None = None
        self._lock = threading.RLock()
        self.configure(voice_name=voice_name, speed=speed, volume=volume)

    @staticmethod
    def _voice_info(voice_name: str) -> tuple[str, str, str]:
        voice_name = str(voice_name or "").strip()
        info = SUPPORTED_TTS_VOICES.get(voice_name)
        if info is None:
            raise TTSConfigurationError(f"Неподдерживаемый голос Piper: {voice_name or '(пусто)'}")
        return info

    def configure(self, voice_name: str, speed: float = DEFAULT_TTS_SPEED, volume: float = DEFAULT_TTS_VOLUME) -> None:
        voice_name = str(voice_name or DEFAULT_TTS_VOICE).strip()
        self._voice_info(voice_name)
        try:
            speed = float(speed)
            volume = float(volume)
        except (TypeError, ValueError) as exc:
            raise TTSConfigurationError("Скорость и громкость TTS должны быть числами.") from exc
        if not 0.7 <= speed <= 1.5:
            raise TTSConfigurationError("Скорость TTS должна находиться в диапазоне 0.7–1.5.")
        if not 0.0 <= volume <= 1.0:
            raise TTSConfigurationError("Громкость TTS должна находиться в диапазоне 0–1.")

        with self._lock:
            if voice_name != self.voice_name:
                self._voice = None
                self._loaded_voice_name = None
            self.voice_name = voice_name
            self.speed = speed
            self.volume = volume

    def paths_for(self, voice_name: str | None = None) -> tuple[Path, Path]:
        selected = voice_name or self.voice_name
        _remote_dir, file_stem, _label = self._voice_info(selected)
        return (
            self.model_dir / f"{file_stem}.onnx",
            self.model_dir / f"{file_stem}.onnx.json",
        )

    def voice_status(self, voice_name: str | None = None) -> str:
        try:
            model_path, config_path = self.paths_for(voice_name)
        except TTSConfigurationError:
            return "unsupported"
        if not model_path.is_file() or not config_path.is_file():
            return "missing"
        try:
            if model_path.stat().st_size < 1024 or config_path.stat().st_size < 100:
                return "missing"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            audio_config = config.get("audio") if isinstance(config, dict) else None
            if not isinstance(audio_config, dict) or int(audio_config.get("sample_rate", 0)) <= 0:
                return "missing"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return "missing"
        return "installed"

    def ensure_voice(self, voice_name: str | None = None) -> Path:
        selected = voice_name or self.voice_name
        remote_dir, file_stem, _label = self._voice_info(selected)
        model_path, config_path = self.paths_for(selected)
        with self._lock:
            self.model_dir.mkdir(parents=True, exist_ok=True)
            if not model_path.is_file() or model_path.stat().st_size < 1024:
                self._download_asset(
                    f"{self.VOICE_ROOT}/{remote_dir}/{file_stem}.onnx?download=true",
                    model_path,
                )
            if not config_path.is_file() or config_path.stat().st_size < 100:
                self._download_asset(
                    f"{self.VOICE_ROOT}/{remote_dir}/{file_stem}.onnx.json?download=true",
                    config_path,
                    max_bytes=2 * 1024 * 1024,
                )
            if self.voice_status(selected) != "installed":
                raise TTSError("Скачанный голос Piper не прошёл проверку файлов.")
        logger.info("tts_voice_installed voice=%s path=%s", selected, model_path)
        return model_path

    @staticmethod
    def _download_asset(url: str, target: Path, max_bytes: int = MAX_VOICE_FILE_BYTES) -> None:
        temporary = target.with_name(target.name + ".part")
        temporary.unlink(missing_ok=True)
        written = 0
        try:
            with requests.get(url, stream=True, timeout=(10, 60), allow_redirects=True) as response:
                final_url = str(getattr(response, "url", url))
                if not final_url.lower().startswith("https://"):
                    raise TTSError("Загрузка голоса остановлена: сервер перенаправил на небезопасный URL.")
                response.raise_for_status()
                declared_size = response.headers.get("Content-Length")
                if declared_size:
                    try:
                        if int(declared_size) > max_bytes:
                            raise TTSError("Файл голоса превышает допустимый размер.")
                    except ValueError:
                        pass
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > max_bytes:
                            raise TTSError("Файл голоса превышает допустимый размер.")
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
            if written < 16:
                raise TTSError("Сервер вернул пустой или слишком маленький файл голоса.")
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        text = prepare_speech_text(text)
        if not text:
            raise TTSError("Нет текста для озвучивания.")
        with self._lock:
            if self.voice_status(self.voice_name) != "installed":
                raise TTSVoiceNotInstalledError(
                    "Голос TTS не установлен. Открой настройки и скачай выбранный голос."
                )
            if self._voice is None or self._loaded_voice_name != self.voice_name:
                try:
                    from piper import PiperVoice

                    model_path, _config_path = self.paths_for()
                    self._voice = PiperVoice.load(model_path)
                    self._loaded_voice_name = self.voice_name
                except Exception as exc:
                    logger.exception("tts_piper_model_load_failed voice=%s", self.voice_name)
                    raise TTSError(
                        "Не удалось загрузить Piper. Проверь установку зависимостей TTS."
                    ) from exc

            try:
                from piper import SynthesisConfig

                synthesis_config = SynthesisConfig(
                    length_scale=1.0 / self.speed,
                    volume=self.volume,
                )
                audio_chunks = list(self._voice.synthesize(text, syn_config=synthesis_config))
                if not audio_chunks:
                    raise TTSError("Piper не вернул аудиоданные.")
                arrays = [
                    np.asarray(chunk.audio_float_array, dtype=np.float32).reshape(-1)
                    for chunk in audio_chunks
                    if np.asarray(chunk.audio_float_array).size
                ]
                if not arrays:
                    raise TTSError("Piper создал пустой аудиофрагмент.")
                audio = np.concatenate(arrays).astype(np.float32, copy=False)
                sample_rate = int(audio_chunks[0].sample_rate)
            except TTSError:
                raise
            except Exception as exc:
                logger.exception("tts_piper_synthesis_failed voice=%s", self.voice_name)
                raise TTSError(f"Ошибка синтеза речи Piper: {exc}") from exc
        return audio, sample_rate
