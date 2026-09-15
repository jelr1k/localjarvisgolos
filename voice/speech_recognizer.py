from __future__ import annotations

import logging

import numpy as np
from faster_whisper import WhisperModel


logger = logging.getLogger("jarvis.voice.whisper")


class SpeechRecognizer:
    """Local faster-whisper speech-to-text recognizer."""

    def __init__(
        self,
        model_name: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "ru",
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            logger.info(
                "whisper_model_loading model=%s device=%s compute_type=%s",
                self.model_name,
                self.device,
                self.compute_type,
            )
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            logger.info("whisper_model_loaded model=%s", self.model_name)
        return self._model

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> str:
        if audio.size == 0:
            return ""

        model = self._get_model()
        audio = np.asarray(audio, dtype=np.float32)
        segments, _info = model.transcribe(
            audio,
            language=self.language or None,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        text = " ".join(text.split())
        logger.info("whisper_transcription_complete chars=%d text=%r", len(text), text)
        return text
