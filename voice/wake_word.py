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

from core.app_paths import APP_DATA_DIR
from voice.devices import (
    find_input_device_by_name,
    find_supported_sample_rate,
    get_shared_input_extra_settings,
    resolve_shared_input_device,
)


logger = logging.getLogger("jarvis.voice.wake_word")

_MODEL_NAME = "vosk-model-small-ru-0.22"
_MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip"
_MODEL_DIR = APP_DATA_DIR / "wake_word" / _MODEL_NAME
_DEFAULT_WAKE_WORD = "Jarvis"
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
    text = _compact(text)
    if not text or any(char in "аеёиоуыэюя" for char in text):
        return text
    replacements = (
        ("shch", "щ"), ("sch", "щ"), ("zh", "ж"), ("kh", "х"), ("ch", "ч"),
        ("sh", "ш"), ("yu", "ю"), ("ju", "ю"), ("ya", "я"), ("ja", "я"),
        ("yo", "е"), ("jo", "е"), ("ye", "е"), ("je", "е"), ("ts", "ц"),
        ("th", "т"), ("ph", "ф"), ("qu", "кв"), ("ck", "к"), ("ee", "и"), ("oo", "у"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    single = {
        "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г",
        "h": "х", "i": "и", "j": "дж", "k": "к", "l": "л", "m": "м", "n": "н",
        "o": "о", "p": "п", "q": "к", "r": "р", "s": "с", "t": "т", "u": "у",
        "v": "в", "w": "в", "x": "кс", "y": "й", "z": "з",
    }
    return "".join(single.get(char, char) for char in text)


def _wake_word_candidates(wake_word: str) -> tuple[str, ...]:
    candidates = []
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

    words = normalized.split()
    for start in range(len(words)):
        joined = ""
        for end in range(start, min(len(words), start + 4)):
            joined += words[end]
            if len(joined) < 3:
                continue
            for candidate in candidates:
                threshold = _SHORT_WORD_THRESHOLD if len(candidate) <= 5 else _FUZZY_THRESHOLD
                if _similarity(joined, candidate) >= threshold:
                    return True
    return False


def _vocabulary_path(model_dir: Path) -> Path:
    return model_dir / "graph" / "words.txt"


def _word_in_vocabulary(model_dir: Path, word: str) -> bool:
    path = _vocabulary_path(model_dir)
    if not path.is_file():
        return False
    targets = {_normalize(v) for v in _wake_word_variants(word) if _normalize(v)}
    try:
        with path.open("r", encoding="utf-8", errors="replace") as file:
            return any(parts and _normalize(parts[0]) in targets for line in file if (parts := line.split()))
    except OSError:
        logger.exception("wake_word_vocabulary_read_failed path=%s", path)
        return False


def _download_model(model_dir: Path) -> Path:
    if model_dir.is_dir() and (model_dir / "am").exists():
        return model_dir
    model_dir.parent.mkdir(parents=True, exist_ok=True)
    archive = model_dir.parent / f"{model_dir.name}.zip"
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
    return model_dir


class WakeWordDetector:
    """Backend Vosk wake-word detector using standard Python threading."""

    def __init__(self, config: dict, event_bus=None):
        self.events = event_bus
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._restart_requested = False
        self.apply_config(config)

    def _emit(self, event: str, *args):
        if self.events is not None:
            self.events.emit(event, *args)

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
            self.device = resolve_shared_input_device(self.device)
            self.sample_rate = find_supported_sample_rate(
                device=self.device, channels=1, preferred=self.sample_rate
            )
        except Exception:
            logger.warning("wake_word_sample_rate_unavailable device=%r", self.device, exc_info=True)

    def start(self):
        if not self.enabled or self.is_running():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="jarvis-wake-word", daemon=True)
        self._thread.start()
        self._emit("wake_word.listening_changed", True)

    def stop(self):
        self._stop_event.set()

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def restart(self):
        self._restart_requested = True
        if not self.is_running():
            self._restart_requested = False
            self.start()
        else:
            self.stop()

    def _run(self):
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel

            SetLogLevel(-1)
            model_dir = _download_model(_MODEL_DIR)
            model = Model(str(model_dir))
            use_grammar = _word_in_vocabulary(model_dir, self.wake_word)
            if use_grammar:
                recognizer = KaldiRecognizer(
                    model, self.sample_rate,
                    json.dumps(list(_wake_word_variants(self.wake_word)), ensure_ascii=False),
                )
            else:
                recognizer = KaldiRecognizer(model, self.sample_rate)

            self._emit("wake_word.status", "Wake word: слушаю")
            audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=32)

            def callback(indata, frames, time_info, status):
                if status:
                    logger.warning("wake_word_stream_status=%s", status)
                if not self._stop_event.is_set():
                    try:
                        audio_queue.put_nowait(bytes(indata))
                    except queue.Full:
                        logger.warning("wake_word_audio_queue_full")

            shared_device = resolve_shared_input_device(self.device)
            extra_settings = get_shared_input_extra_settings(shared_device)
            logger.info(
                "wake_word_stream_opening device=%r samplerate=%s shared_device=%r shared_mode=%s",
                self.device,
                self.sample_rate,
                shared_device,
                extra_settings is not None,
            )
            stream_device = shared_device if shared_device is not None else self.device
            with sd.RawInputStream(
                samplerate=self.sample_rate,
                blocksize=1600,
                device=stream_device,
                dtype="int16",
                channels=1,
                callback=callback,
                extra_settings=extra_settings,
            ):
                while not self._stop_event.is_set():
                    try:
                        data = audio_queue.get(timeout=0.05)
                    except queue.Empty:
                        continue
                    recognizer.AcceptWaveform(data)
                    partial = json.loads(recognizer.PartialResult()).get("partial", "")
                    if partial:
                        self._emit("wake_word.recognized", partial)
                    if _contains_wake_word(partial, self.wake_word):
                        self._emit("wake_word.detected", self.wake_word)
                        self._stop_event.set()
                        break
        except Exception as exc:
            logger.exception("wake_word_failed")
            self._emit("wake_word.error", f"Wake word недоступен: {exc}")
        finally:
            self._emit("wake_word.listening_changed", False)
            self._thread = None
            if self._restart_requested and self.enabled:
                self._restart_requested = False
                timer = threading.Timer(0.1, self.start)
                timer.daemon = True
                timer.start()

    def close(self):
        self._restart_requested = False
        self.stop()
