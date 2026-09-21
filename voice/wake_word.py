from __future__ import annotations

import json
import logging
import queue
import threading
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import sounddevice as sd
from PySide6.QtCore import QObject, QThread, Signal

from core.app_paths import APP_DATA_DIR
from voice.devices import find_input_device_by_name, find_supported_sample_rate


logger = logging.getLogger("jarvis.voice.wake_word")

_MODEL_NAME = "vosk-model-small-ru-0.22"
_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
_MODEL_DIR = APP_DATA_DIR / "wake_word" / _MODEL_NAME
_WAKE_WORDS = ("джарвис", "джервис", "jarvis")


def _normalize(text: str) -> str:
    return " ".join(text.casefold().replace("ё", "е").split())


def _contains_wake_word(text: str) -> bool:
    normalized = _normalize(text)
    return any(word in normalized.split() for word in _WAKE_WORDS)


def _download_model(model_dir: Path) -> Path:
    if model_dir.is_dir() and (model_dir / "am").exists():
        return model_dir

    model_dir.parent.mkdir(parents=True, exist_ok=True)
    archive = model_dir.parent / f"{model_dir.name}.zip"
    logger.info("wake_word_model_downloading url=%s destination=%s", _MODEL_URL, model_dir)

    # Wake-word resources are public and local. Do not inherit HTTP(S) proxy
    # settings from the environment for this download.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(_MODEL_URL, timeout=60) as response, archive.open("wb") as output:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)

    with zipfile.ZipFile(archive) as archive_file:
        archive_file.extractall(model_dir.parent)

    archive.unlink(missing_ok=True)

    if not (model_dir / "am").exists():
        raise RuntimeError(f"Vosk model was extracted incorrectly: {model_dir}")

    logger.info("wake_word_model_ready path=%s", model_dir)
    return model_dir


class _WakeWordWorker(QObject):
    detected = Signal(str)
    status = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, device, sample_rate: int, model_dir: Path):
        super().__init__()
        self.device = device
        self.sample_rate = sample_rate
        self.model_dir = model_dir
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel

            SetLogLevel(-1)
            model = Model(str(self.model_dir))
            grammar = json.dumps(list(_WAKE_WORDS), ensure_ascii=False)
            recognizer = KaldiRecognizer(model, self.sample_rate, grammar)

            self.status.emit("Wake word: слушаю")
            logger.info(
                "wake_word_listening_started device=%r sample_rate=%s grammar=%r",
                self.device,
                self.sample_rate,
                _WAKE_WORDS,
            )

            audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=32)

            def callback(indata, frames, time_info, status):
                if status:
                    logger.warning("wake_word_stream_status=%s", status)
                if not self._stop_event.is_set():
                    try:
                        audio_queue.put_nowait(bytes(indata))
                    except queue.Full:
                        logger.warning("wake_word_audio_queue_full")

            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=1600,
                device=self.device,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while not self._stop_event.is_set():
                    try:
                        data = audio_queue.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    recognizer.AcceptWaveform(data)
                        partial = json.loads(recognizer.PartialResult()).get("partial", "")
                        if _contains_wake_word(partial):
                            logger.info("wake_word_detected partial=%r", partial)
                            self.detected.emit(partial)
                            # One trigger per listening session. MainWindow
                            # restarts the detector after the voice command.
                            self._stop_event.set()
                            break
                    else:
                        self._stop_event.wait(0.01)

            logger.info("wake_word_listening_stopped")
        except Exception as exc:
            logger.exception("wake_word_failed")
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class WakeWordDetector(QObject):
    """Always-on lightweight wake-word detector using Vosk."""

    detected = Signal(str)
    listening_changed = Signal(bool)
    status = Signal(str)
    error = Signal(str)

    def __init__(self, config: dict):
        super().__init__()
        self._thread: QThread | None = None
        self._worker: _WakeWordWorker | None = None
        self.apply_config(config)

    def apply_config(self, config: dict):
        voice_config = config.get("voice", {})
        self.enabled = bool(voice_config.get("wake_word_enabled", True))
        self.wake_word = str(voice_config.get("wake_word", "Jarvis")).strip() or "Jarvis"
        self.device = voice_config.get("input_device")
        device_name = voice_config.get("input_device_name")
        if device_name:
            resolved = find_input_device_by_name(device_name)
            if resolved is not None:
                self.device = int(resolved["index"])
        self.sample_rate = int(voice_config.get("sample_rate", 16000))
        try:
            self.sample_rate = find_supported_sample_rate(
                device=self.device,
                channels=1,
                preferred=self.sample_rate,
            )
        except Exception as exc:
            logger.warning("wake_word_sample_rate_unavailable device=%r error=%r", self.device, exc)

    def start(self):
        if not self.enabled or self.is_running():
            return

        if self.device is None:
            self.status.emit("Wake word: микрофон не выбран")
            logger.warning("wake_word_not_started reason=no_microphone")
            return

        self._thread = QThread()
        self._worker = _WakeWordWorker(self.device, self.sample_rate, _MODEL_DIR)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._run_worker)
        self._worker.detected.connect(self._on_detected)
        self._worker.status.connect(self.status)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)

        self.listening_changed.emit(True)
        self._thread.start()
        logger.info("wake_word_thread_started wake_word=%r", self.wake_word)

    def _run_worker(self):
        try:
            _download_model(_MODEL_DIR)
            self._worker.run()
        except Exception as exc:
            logger.exception("wake_word_worker_start_failed")
            self._worker.failed.emit(str(exc))

    def stop(self):
        if self._worker is not None:
            self._worker.stop()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def _on_detected(self, text: str):
        self.detected.emit(self.wake_word)
        self.status.emit(f"Wake word: «{self.wake_word}»")
        self.listening_changed.emit(False)

    def _on_failed(self, error: str):
        self.listening_changed.emit(False)
        self.error.emit(f"Wake word недоступен: {error}")

    def _on_thread_finished(self):
        logger.debug("wake_word_thread_finished")
        self.listening_changed.emit(False)
        if self._worker is not None:
            self._worker.deleteLater()
        if self._thread is not None:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    def close(self):
        self.stop()
