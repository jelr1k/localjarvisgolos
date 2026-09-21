from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from voice.command_normalizer import normalize_voice_command
from voice.devices import find_input_device_by_name, find_supported_sample_rate
from voice.microphone import MicrophoneRecorder
from voice.speech_recognizer import SpeechRecognizer


logger = logging.getLogger("jarvis.voice")


class _TranscriptionWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, recognizer: SpeechRecognizer, audio, sample_rate: int):
        super().__init__()
        self.recognizer = recognizer
        self.audio = audio
        self.sample_rate = sample_rate

    def run(self):
        try:
            text = self.recognizer.transcribe(self.audio, self.sample_rate)
            logger.info("voice_transcription_worker_finished chars=%d", len(text))
            self.finished.emit(text)
        except Exception as exc:
            logger.exception("voice_transcription_failed")
            self.failed.emit(str(exc))


class VoiceController(QObject):
    """Coordinates push-to-talk recording and background transcription."""

    listening_changed = Signal(bool)
    transcribing_changed = Signal(bool)
    transcript_ready = Signal(str)
    error = Signal(str)

    def __init__(self, config: dict):
        super().__init__()
        self._thread: QThread | None = None
        self._worker: _TranscriptionWorker | None = None
        self.recorder: MicrophoneRecorder | None = None
        self.recognizer: SpeechRecognizer | None = None
        self._silence_timer = QTimer(self)
        self._silence_timer.setInterval(100)
        self._silence_timer.timeout.connect(self._check_silence)
        self.apply_config(config)

    def apply_config(self, config: dict):
        voice_config = config.get("voice", {})
        self.sample_rate = int(voice_config.get("sample_rate", 16000))
        self.channels = int(voice_config.get("channels", 1))
        self.silence_duration = max(
            0.5,
            float(voice_config.get("silence_duration", 2.0)),
        )
        configured_device = voice_config.get("input_device")
        configured_device_name = voice_config.get("input_device_name")

        self.device = configured_device
        if configured_device_name:
            resolved = find_input_device_by_name(configured_device_name)
            if resolved is not None:
                self.device = int(resolved["index"])
                logger.info(
                    "voice_device_restored name=%r index=%s",
                    configured_device_name,
                    self.device,
                )
            else:
                logger.warning(
                    "voice_device_not_found name=%r fallback_index=%r",
                    configured_device_name,
                    configured_device,
                )

        self.model_name = voice_config.get("model", "base")
        self.device_type = voice_config.get("device", "cpu")
        self.compute_type = voice_config.get("compute_type", "int8")
        self.language = voice_config.get("language", "ru")
        self.min_duration = float(voice_config.get("min_duration", 0.25))

        if self.recorder is not None and self.recorder.is_recording:
            self._silence_timer.stop()
            self.recorder.stop()
            self.listening_changed.emit(False)

        self.recorder = None
        self.recording_sample_rate = self.sample_rate
        try:
            self.recording_sample_rate = find_supported_sample_rate(
                device=self.device,
                channels=self.channels,
                preferred=self.sample_rate,
            )
            self.recorder = MicrophoneRecorder(
                sample_rate=self.recording_sample_rate,
                channels=self.channels,
                device=self.device,
            )
        except Exception as exc:
            logger.warning(
                "voice_microphone_unavailable device=%r sample_rate=%s error=%r",
                self.device,
                self.sample_rate,
                exc,
            )

        self.recognizer = SpeechRecognizer(
            model_name=self.model_name,
            device=self.device_type,
            compute_type=self.compute_type,
            language=self.language,
        )
        logger.info(
            "voice_config_applied input_device=%r configured_sample_rate=%s recording_sample_rate=%s microphone_available=%s silence_duration=%.2fs",
            self.device,
            self.sample_rate,
            self.recording_sample_rate,
            self.recorder is not None,
            self.silence_duration,
        )

    @property
    def is_recording(self) -> bool:
        return self.recorder is not None and self.recorder.is_recording

    def start(self):
        if self.recorder is None:
            self.error.emit("Микрофон недоступен. Проверь устройство в настройках голоса.")
            return
        if self.recorder.is_recording or self.transcribing():
            return
        try:
            self.recorder.start()
            self._silence_timer.start()
            self.listening_changed.emit(True)
        except Exception as exc:
            self._silence_timer.stop()
            self.error.emit(self._friendly_microphone_error(exc))

    def stop(self):
        self._silence_timer.stop()
        if self.recorder is None or not self.recorder.is_recording:
            return
        try:
            audio = self.recorder.stop()
            self.listening_changed.emit(False)
        except Exception as exc:
            logger.exception("voice_recording_stop_failed")
            self.listening_changed.emit(False)
            self.error.emit(f"Не удалось остановить запись: {exc}")
            return

        if len(audio) < int(self.recording_sample_rate * self.min_duration):
            logger.info("voice_recording_ignored reason=too_short samples=%d", len(audio))
            return
        self._transcribe(audio)

    def _check_silence(self):
        if self.recorder is None or not self.recorder.is_recording:
            self._silence_timer.stop()
            return
        if not self.recorder.has_voice:
            return
        if self.recorder.silence_duration < self.silence_duration:
            return

        logger.info(
            "voice_recording_auto_stopped silence_duration=%.2fs threshold=%.2fs",
            self.recorder.silence_duration,
            self.silence_duration,
        )
        self.stop()

    def transcribing(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _transcribe(self, audio):
        if self.recognizer is None:
            self.error.emit("Распознаватель речи не инициализирован.")
            return
        self.transcribing_changed.emit(True)
        self._thread = QThread()
        self._worker = _TranscriptionWorker(
            self.recognizer,
            audio,
            self.recording_sample_rate,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_transcript)
        self._worker.failed.connect(self._on_error)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()
        logger.debug("voice_transcription_thread_started")

    def _on_transcript(self, text: str):
        logger.info("voice_transcription_result_received chars=%d", len(text))
        raw_text = text.strip()
        if not raw_text:
            logger.info("voice_transcription_empty")
            self.transcribing_changed.emit(False)
            self._quit_transcription_thread()
            return

        normalized_text = normalize_voice_command(raw_text)
        logger.info(
            "voice_command_normalized raw=%r normalized=%r changed=%s",
            raw_text,
            normalized_text,
            raw_text != normalized_text,
        )
        if normalized_text:
            logger.info("voice_transcript_ready text=%r", normalized_text)
            self.transcript_ready.emit(normalized_text)
        else:
            logger.info("voice_command_normalized_empty raw=%r", raw_text)

        self.transcribing_changed.emit(False)
        self._quit_transcription_thread()

    def _on_error(self, error: str):
        self.transcribing_changed.emit(False)
        self.error.emit(f"Не удалось распознать речь: {error}")
        self._quit_transcription_thread()

    def _quit_transcription_thread(self):
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()

    def _on_thread_finished(self):
        logger.debug("voice_transcription_thread_finished")
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    @staticmethod
    def _friendly_microphone_error(exc: Exception) -> str:
        return (
            "Не удалось подключиться к выбранному микрофону. Проверь, что он подключён "
            f"и JARVIS имеет доступ к нему. Детали: {exc}"
        )

    def close(self):
        self._silence_timer.stop()
        if self.recorder is not None and self.recorder.is_recording:
            self.recorder.stop()
            self.listening_changed.emit(False)
