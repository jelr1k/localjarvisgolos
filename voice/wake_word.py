from __future__ import annotations

import json
import logging
import queue
import threading
import urllib.request
import zipfile
from difflib import SequenceMatcher
from pathlib import Path

import sounddevice as sd
from PySide6.QtCore import QObject, QThread, Signal, QTimer

from core.app_paths import APP_DATA_DIR
from voice.devices import find_input_device_by_name, find_supported_sample_rate


logger = logging.getLogger("jarvis.voice.wake_word")

_MODEL_NAME = "vosk-model-small-ru-0.22"
_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
_MODEL_DIR = APP_DATA_DIR / "wake_word" / _MODEL_NAME
_DEFAULT_WAKE_WORD = "Jarvis"

# Vosk's runtime grammar only accepts words that already exist in the model
# vocabulary. For a user-defined word that is absent from the dictionary we
# fall back to unrestricted Vosk recognition and fuzzy matching against the
# requested wake word. This keeps the Vosk backend and allows arbitrary
# user-entered words without rebuilding a Kaldi graph on every settings change.
_FUZZY_THRESHOLD = 0.78
_SHORT_WORD_THRESHOLD = 0.88


def _normalize(text: str) -> str:
    return " ".join(text.casefold().replace("ё", "е").split())


def _compact(text: str) -> str:
    return "".join(_normalize(text).split())


def _wake_word_variants(wake_word: str) -> tuple[str, ...]:
    normalized = _normalize(wake_word)
    if normalized == "jarvis":
        return ("джарвис", "джервис", "jarvis")
    return (normalized,) if normalized else (_normalize(_DEFAULT_WAKE_WORD),)


def _transliterate_to_russian(text: str) -> str:
    """Return a rough Russian phonetic spelling for Latin wake words."""
    text = _compact(text)
    if not text or any(char in "аеёиоуыэюя" for char in text):
        return text

    # Longest sequences first. This is deliberately phonetic, not linguistic:
    # the result is only used as an additional fuzzy-match candidate.
    replacements = (
        ("shch", "щ"),
        ("sch", "щ"),
        ("zh", "ж"),
        ("kh", "х"),
        ("ch", "ч"),
        ("sh", "ш"),
        ("yu", "ю"),
        ("ju", "ю"),
        ("ya", "я"),
        ("ja", "я"),
        ("yo", "е"),
        ("jo", "е"),
        ("ye", "е"),
        ("je", "е"),
        ("ts", "ц"),
        ("th", "т"),
        ("ph", "ф"),
        ("qu", "кв"),
        ("ck", "к"),
        ("ee", "и"),
        ("oo", "у"),
    )
    for source, target in replacements:
        text = text.replace(source, target)

    single = {
        "a": "а",
        "b": "б",
        "c": "к",
        "d": "д",
        "e": "е",
        "f": "ф",
        "g": "г",
        "h": "х",
        "i": "и",
        "j": "дж",
        "k": "к",
        "l": "л",
        "m": "м",
        "n": "н",
        "o": "о",
        "p": "п",
        "q": "к",
        "r": "р",
        "s": "с",
        "t": "т",
        "u": "у",
        "v": "в",
        "w": "в",
        "x": "кс",
        "y": "й",
        "z": "з",
    }
    return "".join(single.get(char, char) for char in text)


def _wake_word_candidates(wake_word: str) -> tuple[str, ...]:
    candidates: list[str] = []
    for variant in _wake_word_variants(wake_word):
        for candidate in (variant, _transliterate_to_russian(variant)):
            compact = _compact(candidate)
            if compact and compact not in candidates:
                candidates.append(compact)
    return tuple(candidates)


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, _compact(left), _compact(right)).ratio()


def _contains_wake_word(text: str, wake_word: str) -> bool:
    normalized = _normalize(text)
    if not normalized:
        return False

    compact_text = _compact(normalized)
    candidates = _wake_word_candidates(wake_word)

    for candidate in candidates:
        if candidate in compact_text:
            return True

    # Check individual words and short word groups. This catches Vosk outputs
    # such as "джел рик" when the configured wake word is "Джелрик".
    words = normalized.split()
    for start in range(len(words)):
        joined = ""
        for end in range(start, min(len(words), start + 4)):
            joined += words[end]
            if len(joined) < 3:
                continue
            for candidate in candidates:
                score = _similarity(joined, candidate)
                threshold = (
                    _SHORT_WORD_THRESHOLD
                    if len(candidate) <= 5
                    else _FUZZY_THRESHOLD
                )
                if score >= threshold:
                    logger.debug(
                        "wake_word_fuzzy_match candidate=%r recognized=%r score=%.3f",
                        candidate,
                        joined,
                        score,
                    )
                    return True

    return False


def _vocabulary_path(model_dir: Path) -> Path:
    return model_dir / "graph" / "words.txt"


def _word_in_vocabulary(model_dir: Path, word: str) -> bool:
    """Check whether any configured wake-word variant is in Vosk's graph."""
    vocabulary_path = _vocabulary_path(model_dir)
    if not vocabulary_path.is_file():
        logger.warning("wake_word_vocabulary_missing path=%s", vocabulary_path)
        return False

    targets = {
        _normalize(variant)
        for variant in _wake_word_variants(word)
        if _normalize(variant)
    }
    if not targets:
        return False

    try:
        with vocabulary_path.open("r", encoding="utf-8", errors="replace") as file:
            for line in file:
                parts = line.split()
                if parts and _normalize(parts[0]) in targets:
                    return True
    except OSError:
        logger.exception("wake_word_vocabulary_read_failed path=%s", vocabulary_path)
    return False


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

    def __init__(self, device, sample_rate: int, model_dir: Path, wake_word: str):
        super().__init__()
        self.device = device
        self.sample_rate = sample_rate
        self.model_dir = model_dir
        self.wake_word = wake_word
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel

            SetLogLevel(-1)
            model_dir = _download_model(self.model_dir)
            model = Model(str(model_dir))

            use_grammar = _word_in_vocabulary(model_dir, self.wake_word)
            if use_grammar:
                grammar_words = _wake_word_variants(self.wake_word)
                grammar = json.dumps(list(grammar_words), ensure_ascii=False)
                recognizer = KaldiRecognizer(model, self.sample_rate, grammar)
                logger.info(
                    "wake_word_mode=grammar wake_word=%r grammar=%r",
                    self.wake_word,
                    grammar_words,
                )
            else:
                # An unknown word cannot be inserted into a Vosk grammar just
                # by putting its spelling into JSON. The small model's graph
                # must already contain the word. Unrestricted recognition lets
                # us match Vosk's closest transcription instead.
                recognizer = KaldiRecognizer(model, self.sample_rate)
                logger.info(
                    "wake_word_mode=fuzzy wake_word=%r candidates=%r",
                    self.wake_word,
                    _wake_word_candidates(self.wake_word),
                )

            self.status.emit("Wake word: слушаю")
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
                    if _contains_wake_word(partial, self.wake_word):
                        logger.info(
                            "wake_word_detected partial=%r mode=%s",
                            partial,
                            "grammar" if use_grammar else "fuzzy",
                        )
                        self.detected.emit(partial)
                        # One trigger per listening session. MainWindow
                        # restarts the detector after the voice command.
                        self._stop_event.set()
                        break

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
        self._restart_requested = False
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
            logger.warning(
                "wake_word_sample_rate_unavailable device=%r error=%r",
                self.device,
                exc,
            )

    def start(self):
        if not self.enabled or self.is_running():
            return

        self._thread = QThread()
        self._worker = _WakeWordWorker(
            self.device,
            self.sample_rate,
            _MODEL_DIR,
            self.wake_word,
        )
        self._worker.moveToThread(self._thread)

        # The worker itself must receive thread.started. Connecting it to
        # WakeWordDetector._run_worker would execute _worker.run() in the
        # GUI thread because WakeWordDetector lives there.
        self._thread.started.connect(self._worker.run)
        self._worker.detected.connect(self._on_detected)
        self._worker.status.connect(self.status)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._thread.quit)
        self._thread.finished.connect(self._on_thread_finished)

        self.listening_changed.emit(True)
        self._thread.start()
        logger.info("wake_word_thread_started wake_word=%r", self.wake_word)

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
        if self._restart_requested and self.enabled:
            self._restart_requested = False
            QTimer.singleShot(100, self.start)

    def restart(self):
        self._restart_requested = True
        if not self.is_running():
            self._restart_requested = False
            self.start()
        else:
            self.stop()

    def close(self):
        self.stop()
