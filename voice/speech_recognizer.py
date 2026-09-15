from __future__ import annotations

import logging

import numpy as np
from faster_whisper import WhisperModel


logger = logging.getLogger("jarvis.voice.whisper")

_TARGET_SAMPLE_RATE = 16000


class SpeechRecognizer:
    """Local faster-whisper speech-to-text recognizer."""

    def __init__(
        self,
        model_name: str = "small",
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

    @staticmethod
    def _resample(audio: np.ndarray, source_rate: int, target_rate: int = _TARGET_SAMPLE_RATE) -> np.ndarray:
        source_rate = int(source_rate)
        target_rate = int(target_rate)
        if source_rate <= 0 or source_rate == target_rate or audio.size < 2:
            return audio

        target_length = max(1, round(len(audio) * target_rate / source_rate))
        source_positions = np.arange(len(audio), dtype=np.float64)
        target_positions = np.linspace(0, len(audio) - 1, target_length, dtype=np.float64)
        return np.asarray(np.interp(target_positions, source_positions, audio), dtype=np.float32)

    def transcribe(self, audio: np.ndarray, sample_rate: int = _TARGET_SAMPLE_RATE) -> str:
        if audio.size == 0:
            return ""

        audio = np.asarray(audio, dtype=np.float32)
        if int(sample_rate) != _TARGET_SAMPLE_RATE:
            logger.info(
                "whisper_audio_resampling source_rate=%s target_rate=%s samples=%d",
                sample_rate,
                _TARGET_SAMPLE_RATE,
                len(audio),
            )
            audio = self._resample(audio, sample_rate, _TARGET_SAMPLE_RATE)

        model = self._get_model()
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
