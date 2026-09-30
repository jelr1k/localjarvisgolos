from __future__ import annotations

from dataclasses import dataclass


@dataclass
class WhisperStats:
    model: str = ""
    load_time_s: float = 0.0
    transcription_time_s: float = 0.0
    audio_duration_s: float = 0.0
    real_time_factor: float = 0.0
    unload_time_s: float | None = None
    beam_size: int = 5
    cpu_threads: int = 0
    device: str = ""
    compute_type: str = ""
