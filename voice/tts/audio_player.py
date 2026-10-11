from __future__ import annotations

import logging
from typing import Protocol

import numpy as np

logger = logging.getLogger("jarvis.tts")

class AudioPlayer(Protocol):
    def play(self, audio: np.ndarray, sample_rate: int) -> None: ...
    def stop(self) -> None: ...


class SoundDevicePlayer:
    """Blocking playback adapter; TTS worker keeps it off the UI thread."""

    def play(self, audio: np.ndarray, sample_rate: int) -> None:
        import sounddevice as sd

        sd.play(np.asarray(audio, dtype=np.float32), samplerate=int(sample_rate), blocking=True)

    def stop(self) -> None:
        try:
            import sounddevice as sd

            sd.stop()
        except Exception:
            logger.debug("tts_audio_stop_failed", exc_info=True)
