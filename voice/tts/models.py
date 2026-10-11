"""Engine-independent voice and speech-request data contracts."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


@dataclass(frozen=True, slots=True)
class VoiceProfile:
    voice_id: str
    display_name: str
    engine_id: str
    model_id: str
    kind: str = "builtin"
    settings: dict[str, Any] = field(default_factory=dict)
    reference_audio: str | None = None
    reference_text: str | None = None
    enabled: bool = True

    def __post_init__(self) -> None:
        for field_name in ("voice_id", "engine_id", "model_id"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not _ID_PATTERN.fullmatch(value):
                raise ValueError(f"Invalid {field_name}: {value!r}")
        if not isinstance(self.display_name, str) or not self.display_name.strip():
            raise ValueError("display_name must not be empty")
        if self.kind not in {"builtin", "custom"}:
            raise ValueError("kind must be 'builtin' or 'custom'")
        if not isinstance(self.settings, dict):
            raise ValueError("settings must be a dictionary")
        object.__setattr__(self, "settings", dict(self.settings))
        if self.reference_audio is not None:
            object.__setattr__(self, "reference_audio", str(self.reference_audio))
        if self.reference_text is not None:
            object.__setattr__(self, "reference_text", str(self.reference_text))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "VoiceProfile":
        settings = value.get("settings", {})
        return cls(
            voice_id=str(value["voice_id"]),
            display_name=str(value["display_name"]),
            engine_id=str(value["engine_id"]),
            model_id=str(value["model_id"]),
            kind=str(value.get("kind", "custom")),
            settings=settings if isinstance(settings, dict) else {},
            reference_audio=value.get("reference_audio"),
            reference_text=value.get("reference_text"),
            enabled=bool(value.get("enabled", True)),
        )


@dataclass(frozen=True, slots=True)
class SpeechRequest:
    text: str
    source: str = "assistant"
    response_key: str | None = None
    voice_id: str | None = None
    cache_policy: str = "use"

    def __post_init__(self) -> None:
        if self.cache_policy not in {"use", "bypass", "refresh"}:
            raise ValueError("cache_policy must be use, bypass, or refresh")
        if self.response_key is not None and not str(self.response_key).strip():
            object.__setattr__(self, "response_key", None)
