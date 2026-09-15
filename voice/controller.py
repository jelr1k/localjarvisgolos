from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, Signal

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
            self.finished.emit(self.recognizer.transcribe(self.audio, self.sample_rate))
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
        self.apply_config(config)

    def apply_config(self, config: dict):
        voice_config = config.get("voice", {})
        self.sample_rate = int(voice_config.get("sample_rate", 16000))
        self.channels = int(voice_config.get("channels", 1))
        configured_device = voice_config.get("input_device")
        configured_device_name = voice_config.get("input_device_name")

        # PortAudio indexes can change after reboot, driver changes, or when
        # Windows exposes devices in a different order. Prefer the saved stable
        # device name and only fall back to the old numeric index for legacy configs.
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
            self.recorder.stop()
            self.listening_changed.emit(False)

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
        self.recognizer = SpeechRecognizer(
            model_name=self.model_name,
            device=self.device_type,
            compute_type=self.compute_type,
            language=self.language,
        )
        logger.info(
            "voice_config_applied input_device=%r configured_sample_rate=%s recording_sample_rate=%s",
            self.device,
            self.sample_rate,
            self.recording_sample_rate,
        )

    @property
    def is_recording(self) -> bool:
        return self.recorder is not None and self.recorder.is_recording

    def start(self):
        if self.recorder is None or self.recorder.is_recording or self.transcribing():
            return
        try:
            self.recorder.start()
            self.listening_changed.emit(True)
        except Exception as exc:
            self.error.emit(self._friendly_microphone_error(exc))

    def stop(self):
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
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

    def _on_transcript(self, text: str):
        self.transcribing_changed.emit(False)
        if text.strip():
            self.transcript_ready.emit(text.strip())
        else:
            logger.info("voice_transcription_empty")

    def _on_error(self, error: str):
        self.transcribing_changed.emit(False)
        self.error.emit(f"Не удалось распознать речь: {error}")

    def _on_thread_finished(self):
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
        if self.recorder is not None and self.recorder.is_recording:
            self.recorder.stop()
            self.listening_changed.emit(False)
