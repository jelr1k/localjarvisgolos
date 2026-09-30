from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from core.dependency_manager import get_dependency_manager


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
        cpu_threads: int = 4,
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.cpu_threads = max(1, int(cpu_threads))
        self._model: WhisperModel | None = None
        self._model_load_duration_s: float | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            model_source = self.model_name
            local_path = Path(model_source).expanduser()
            if local_path.is_dir():
                model_source = str(local_path.resolve())
                logger.info(
                    "whisper_local_model_detected path=%s",
                    model_source,
                )

            if not local_path.is_dir():
                prepare_started = time.perf_counter()
                logger.info("whisper_model_prepare_started model=%s", model_source)
                get_dependency_manager().ensure_whisper_model(model_source)
                logger.info(
                    "whisper_model_prepare_complete model=%s duration_s=%.3f",
                    model_source,
                    time.perf_counter() - prepare_started,
                )

            logger.info(
                "whisper_model_loading model=%s device=%s compute_type=%s",
                model_source,
                self.device,
                self.compute_type,
            )
            model_started = time.perf_counter()
            self._model = WhisperModel(
                model_source,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
            self._model_load_duration_s = time.perf_counter() - model_started
            logger.info(
                "whisper_model_loaded model=%s duration_s=%.3f cpu_threads=%d",
                model_source,
                self._model_load_duration_s,
                self.cpu_threads,
            )
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
        transcription_started = time.perf_counter()
        audio_duration_s = len(audio) / _TARGET_SAMPLE_RATE
        logger.info(
            "whisper_transcription_started audio_duration_s=%.3f samples=%d",
            audio_duration_s,
            len(audio),
        )
        segments, _info = model.transcribe(
            audio,
            language=self.language or None,
            beam_size=5,
            vad_filter=True,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        text = " ".join(text.split())
        transcription_duration_s = time.perf_counter() - transcription_started
        real_time_factor = (
            transcription_duration_s / audio_duration_s
            if audio_duration_s > 0
            else 0.0
        )
        logger.info(
            "whisper_transcription_complete duration_s=%.3f audio_duration_s=%.3f "
            "real_time_factor=%.3f chars=%d text=%r",
            transcription_duration_s,
            audio_duration_s,
            real_time_factor,
            len(text),
            text,
        )
        return text
