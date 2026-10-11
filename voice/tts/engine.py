"""Engine-independent contract for local or external TTS adapters."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class TTSBackend(Protocol):
    """Minimal adapter contract consumed by TTSService."""
    engine_id: str
    voice_name: str
    speed: float
    volume: float

    def configure(self, voice_name: str, speed: float = 1.0, volume: float = 0.85) -> None: ...
    def voice_status(self, voice_name: str | None = None) -> str: ...
    def ensure_voice(self, voice_name: str | None = None) -> Path: ...
    def synthesize(self, text: str) -> tuple[np.ndarray, int]: ...
