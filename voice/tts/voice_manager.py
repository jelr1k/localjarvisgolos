"""Persistent voice-profile catalog stored in user AppData."""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Iterable

from core.app_paths import APP_DATA_DIR
from .models import VoiceProfile

logger = logging.getLogger("jarvis.tts.voices")


class VoiceManager:
    """Manage built-in and user-defined profiles independently from the active engine.

    Reference audio/transcript fields are metadata for a future cloning-capable engine;
    storing a sample does not make Piper capable of cloning a voice.
    """

    def __init__(self, storage_path: str | Path | None = None, builtin_profiles: Iterable[VoiceProfile] = ()) -> None:
        self.storage_path = Path(storage_path) if storage_path is not None else APP_DATA_DIR / "tts" / "voice_profiles.json"
        self._lock = threading.RLock()
        self._builtins: dict[str, VoiceProfile] = {}
        for profile in builtin_profiles:
            if profile.kind != "builtin":
                raise ValueError("builtin_profiles may only contain kind='builtin' profiles")
            if profile.voice_id in self._builtins:
                raise ValueError(f"Duplicate built-in voice: {profile.voice_id}")
            self._builtins[profile.voice_id] = profile
        self._custom: dict[str, VoiceProfile] = {}
        self._active_voice_id: str | None = next(iter(self._builtins), None)
        self._load()

    def _all(self) -> dict[str, VoiceProfile]:
        return {**self._builtins, **self._custom}

    def list_voices(self, include_disabled: bool = False) -> list[VoiceProfile]:
        with self._lock:
            profiles = list(self._all().values())
            return profiles if include_disabled else [profile for profile in profiles if profile.enabled]

    def get_voice(self, voice_id: str) -> VoiceProfile:
        with self._lock:
            try:
                return self._all()[voice_id]
            except KeyError as exc:
                raise KeyError(f"Unknown voice profile: {voice_id}") from exc

    def add_voice(self, profile: VoiceProfile) -> None:
        if profile.kind != "custom":
            raise ValueError("Only custom profiles can be added at runtime")
        with self._lock:
            if profile.voice_id in self._all():
                raise ValueError(f"Voice profile already exists: {profile.voice_id}")
            self._custom[profile.voice_id] = profile
            if self._active_voice_id is None:
                self._active_voice_id = profile.voice_id
            self._save()

    def remove_voice(self, voice_id: str) -> None:
        with self._lock:
            if voice_id in self._builtins:
                raise ValueError("Built-in voice profiles cannot be removed")
            if voice_id not in self._custom:
                raise KeyError(f"Unknown custom voice profile: {voice_id}")
            del self._custom[voice_id]
            if self._active_voice_id == voice_id:
                self._active_voice_id = next(iter(self._all()), None)
            self._save()

    def set_active_voice(self, voice_id: str) -> VoiceProfile:
        with self._lock:
            profile = self._all().get(voice_id)
            if profile is None:
                raise KeyError(f"Unknown voice profile: {voice_id}")
            if not profile.enabled:
                raise ValueError(f"Voice profile is disabled: {voice_id}")
            self._active_voice_id = voice_id
            self._save()
            return profile

    @property
    def active_voice_id(self) -> str | None:
        with self._lock:
            return self._active_voice_id

    @property
    def active_voice(self) -> VoiceProfile | None:
        with self._lock:
            return self._all().get(self._active_voice_id) if self._active_voice_id else None

    def _load(self) -> None:
        if not self.storage_path.is_file():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            entries = data.get("profiles", []) if isinstance(data, dict) else []
            if isinstance(entries, list):
                for item in entries:
                    if not isinstance(item, dict):
                        continue
                    try:
                        profile = VoiceProfile.from_dict(item)
                        if profile.kind == "custom" and profile.voice_id not in self._builtins:
                            self._custom[profile.voice_id] = profile
                    except (KeyError, TypeError, ValueError):
                        logger.warning("tts_voice_profile_ignored path=%s", self.storage_path)
            active = data.get("active_voice_id") if isinstance(data, dict) else None
            if active in self._all():
                self._active_voice_id = active
            elif self._active_voice_id not in self._all():
                self._active_voice_id = next(iter(self._all()), None)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("tts_voice_profiles_load_failed path=%s error=%s", self.storage_path, exc)

    def _save(self) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": 1,
            "active_voice_id": self._active_voice_id,
            "profiles": [profile.to_dict() for profile in self._custom.values()],
        }
        temporary = self.storage_path.with_suffix(self.storage_path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.storage_path)
