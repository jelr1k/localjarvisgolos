from __future__ import annotations

import gc
import logging
import time
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from core.dependency_manager import get_dependency_manager
from voice.statistics import WhisperStats


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
        beam_size: int = 5,
        vad_filter: bool = True,
        without_timestamps: bool = True,
        condition_on_previous_text: bool = False,
    ):
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.cpu_threads = max(1, int(cpu_threads))
        self.beam_size = max(1, int(beam_size))
        self.vad_filter = bool(vad_filter)
        self.without_timestamps = bool(without_timestamps)
        self.condition_on_previous_text = bool(condition_on_previous_text)
        self._model: WhisperModel | None = None
        self._model_load_duration_s: float | None = None
        self._last_model_prepare_duration_s: float = 0.0
        self._last_model_load_duration_s: float = 0.0
        self._last_model_loaded_this_request: bool = False
        self._last_stats: WhisperStats | None = None

    @property
    def last_stats(self) -> WhisperStats | None:
        return self._last_stats

    def update_settings(self, *, beam_size: int | None = None, vad_filter: bool | None = None, without_timestamps: bool | None = None, condition_on_previous_text: bool | None = None) -> None:
        if beam_size is not None:
            self.beam_size = max(1, int(beam_size))
        if vad_filter is not None:
            self.vad_filter = bool(vad_filter)
        if without_timestamps is not None:
            self.without_timestamps = bool(without_timestamps)
        if condition_on_previous_text is not None:
            self.condition_on_previous_text = bool(condition_on_previous_text)

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
                self._last_model_prepare_duration_s = time.perf_counter() - prepare_started
                logger.info(
                    "whisper_model_prepare_complete model=%s duration_s=%.3f",
                    model_source,
                    self._last_model_prepare_duration_s,
                )

            logger.info(
                "whisper_model_loading model=%s device=%s compute_type=%s",
                model_source,
                self.device,
                self.compute_type,
            )
            model_started = time.perf_counter()
            self._last_model_loaded_this_request = True
            self._model = WhisperModel(
                model_source,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
            self._model_load_duration_s = time.perf_counter() - model_started
            self._last_model_load_duration_s = self._model_load_duration_s
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
        request_started = time.perf_counter()
        self._last_model_loaded_this_request = False
        self._last_model_prepare_duration_s = 0.0
        self._last_model_load_duration_s = 0.0
        if audio.size == 0:
            return ""

        audio = np.asarray(audio, dtype=np.float32)
        audio_prepare_started = time.perf_counter()
        if int(sample_rate) != _TARGET_SAMPLE_RATE:
            logger.info(
                "whisper_audio_resampling source_rate=%s target_rate=%s samples=%d",
                sample_rate,
                _TARGET_SAMPLE_RATE,
                len(audio),
            )
            audio = self._resample(audio, sample_rate, _TARGET_SAMPLE_RATE)
        audio_prepare_duration_s = time.perf_counter() - audio_prepare_started

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
            beam_size=self.beam_size,
            vad_filter=self.vad_filter,
            without_timestamps=self.without_timestamps,
            condition_on_previous_text=self.condition_on_previous_text,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip())
        text = " ".join(text.split())
        transcription_duration_s = time.perf_counter() - transcription_started
        total_duration_s = time.perf_counter() - request_started
        real_time_factor = (
            transcription_duration_s / audio_duration_s
            if audio_duration_s > 0
            else 0.0
        )
        self._last_stats = WhisperStats(
            model=self.model_name,
            load_time_s=self._model_load_duration_s or 0.0,
            transcription_time_s=transcription_duration_s,
            audio_duration_s=audio_duration_s,
            real_time_factor=real_time_factor,
            unload_time_s=None,
            beam_size=self.beam_size,
            cpu_threads=self.cpu_threads,
            device=self.device,
            compute_type=self.compute_type,
            model_prepare_time_s=self._last_model_prepare_duration_s,
            model_load_time_s=self._last_model_load_duration_s,
            audio_prepare_time_s=audio_prepare_duration_s,
            total_time_s=total_duration_s,
            model_loaded_this_request=self._last_model_loaded_this_request,
            vad_filter=self.vad_filter,
            without_timestamps=self.without_timestamps,
            condition_on_previous_text=self.condition_on_previous_text,
        )
        logger.info(
            "whisper_transcription_complete duration_s=%.3f audio_duration_s=%.3f "
            "real_time_factor=%.3f model_prepare_time_s=%.3f model_load_time_s=%.3f "
            "audio_prepare_time_s=%.3f total_time_s=%.3f model_loaded_this_request=%s "
            "beam_size=%d vad_filter=%s without_timestamps=%s condition_on_previous_text=%s chars=%d text=%r",
            transcription_duration_s,
            audio_duration_s,
            real_time_factor,
            self._last_model_prepare_duration_s,
            self._last_model_load_duration_s,
            audio_prepare_duration_s,
            total_duration_s,
            self._last_model_loaded_this_request,
            self.beam_size,
            self.vad_filter,
            self.without_timestamps,
            self.condition_on_previous_text,
            len(text),
            text,
        )
        return text

    def close(self) -> WhisperStats | None:
        if self._model is None:
            return self._last_stats

        started = time.perf_counter()
        self._model = None
        gc.collect()
        duration = time.perf_counter() - started
        if self._last_stats is not None:
            self._last_stats.unload_time_s = duration
        logger.info(
            "whisper_model_unloaded model=%s duration_s=%.3f",
            self.model_name,
            duration,
        )
        return self._last_stats
