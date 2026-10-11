from __future__ import annotations

import json
import logging
import os
import queue
import re
import threading
from pathlib import Path
from typing import Protocol

import numpy as np
import requests

from core.app_paths import APP_DATA_DIR


logger = logging.getLogger("jarvis.tts")

DEFAULT_TTS_VOICE = "ru_RU-dmitri-medium"
DEFAULT_TTS_SPEED = 1.0
DEFAULT_TTS_VOLUME = 0.85
MAX_SPEECH_CHARS = 16000
SPEECH_CHUNK_CHARS = 420
MAX_VOICE_FILE_BYTES = 256 * 1024 * 1024

# Explicit allow-list keeps model downloads restricted to known HTTPS assets.
SUPPORTED_TTS_VOICES = {
    "ru_RU-dmitri-medium": (
        "ru/ru_RU/dmitri/medium",
        "ru_RU-dmitri-medium",
        "Дмитрий · русский · medium",
    ),
    "ru_RU-irina-medium": (
        "ru/ru_RU/irina/medium",
        "ru_RU-irina-medium",
        "Ирина · русский · medium",
    ),
    "ru_RU-ruslan-medium": (
        "ru/ru_RU/ruslan/medium",
        "ru_RU-ruslan-medium",
        "Руслан · русский · medium",
    ),
}


class TTSError(RuntimeError):
    """Base exception for text-to-speech failures."""


class TTSVoiceNotInstalledError(TTSError):
    """Raised when the configured voice model has not been downloaded yet."""


class TTSConfigurationError(TTSError):
    """Raised when the selected voice or synthesis parameters are invalid."""


class AudioPlayer(Protocol):
    def play(self, audio: np.ndarray, sample_rate: int) -> None: ...
    def stop(self) -> None: ...


def prepare_speech_text(value: str) -> str:
    """Remove common Markdown and code noise before sending text to TTS."""
    text = str(value or "")
    text = re.sub(r"\x60{3}.*?\x60{3}", " ", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)", r"\1", text)
    text = re.sub(r"\x60[^\x60]*\x60", " ", text)
    text = re.sub(r"https?://\S+", " ссылка ", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"[*_~]{1,3}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_SPEECH_CHARS:
        text = text[:MAX_SPEECH_CHARS].rsplit(" ", 1)[0].rstrip() + ". Остальная часть ответа не озвучена."
    return text


def split_speech_text(value: str, max_chars: int = SPEECH_CHUNK_CHARS) -> list[str]:
    """Split long answers near sentence boundaries so playback can start early."""
    text = prepare_speech_text(value)
    max_chars = max(80, int(max_chars))
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?…])\s+|\n+", text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
            if cut < 1:
                cut = max_chars
            part, sentence = sentence[:cut].strip(), sentence[cut:].strip()
            if current:
                chunks.append(current)
                current = ""
            if part:
                chunks.append(part)
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


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


class PiperTTSBackend:
    """Lazy local Piper backend. Voice files live in AppData, not in the repository."""

    VOICE_ROOT = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

    def __init__(
        self,
        model_dir: str | Path | None = None,
        voice_name: str = DEFAULT_TTS_VOICE,
        speed: float = DEFAULT_TTS_SPEED,
        volume: float = DEFAULT_TTS_VOLUME,
    ):
        self.model_dir = Path(model_dir) if model_dir is not None else APP_DATA_DIR / "tts" / "voices"
        self.voice_name = DEFAULT_TTS_VOICE
        self.speed = DEFAULT_TTS_SPEED
        self.volume = DEFAULT_TTS_VOLUME
        self._voice = None
        self._loaded_voice_name: str | None = None
        self._lock = threading.RLock()
        self.configure(voice_name=voice_name, speed=speed, volume=volume)

    @staticmethod
    def _voice_info(voice_name: str) -> tuple[str, str, str]:
        voice_name = str(voice_name or "").strip()
        info = SUPPORTED_TTS_VOICES.get(voice_name)
        if info is None:
            raise TTSConfigurationError(f"Неподдерживаемый голос Piper: {voice_name or '(пусто)'}")
        return info

    def configure(self, voice_name: str, speed: float = DEFAULT_TTS_SPEED, volume: float = DEFAULT_TTS_VOLUME) -> None:
        voice_name = str(voice_name or DEFAULT_TTS_VOICE).strip()
        self._voice_info(voice_name)
        try:
            speed = float(speed)
            volume = float(volume)
        except (TypeError, ValueError) as exc:
            raise TTSConfigurationError("Скорость и громкость TTS должны быть числами.") from exc
        if not 0.7 <= speed <= 1.5:
            raise TTSConfigurationError("Скорость TTS должна находиться в диапазоне 0.7–1.5.")
        if not 0.0 <= volume <= 1.0:
            raise TTSConfigurationError("Громкость TTS должна находиться в диапазоне 0–1.")

        with self._lock:
            if voice_name != self.voice_name:
                self._voice = None
                self._loaded_voice_name = None
            self.voice_name = voice_name
            self.speed = speed
            self.volume = volume

    def paths_for(self, voice_name: str | None = None) -> tuple[Path, Path]:
        selected = voice_name or self.voice_name
        _remote_dir, file_stem, _label = self._voice_info(selected)
        return (
            self.model_dir / f"{file_stem}.onnx",
            self.model_dir / f"{file_stem}.onnx.json",
        )

    def voice_status(self, voice_name: str | None = None) -> str:
        try:
            model_path, config_path = self.paths_for(voice_name)
        except TTSConfigurationError:
            return "unsupported"
        if not model_path.is_file() or not config_path.is_file():
            return "missing"
        try:
            if model_path.stat().st_size < 1024 or config_path.stat().st_size < 100:
                return "missing"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if not isinstance(config, dict) or int(config.get("audio", {}).get("sample_rate", 0)) <= 0:
                return "missing"
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return "missing"
        return "installed"

    def ensure_voice(self, voice_name: str | None = None) -> Path:
        selected = voice_name or self.voice_name
        remote_dir, file_stem, _label = self._voice_info(selected)
        model_path, config_path = self.paths_for(selected)
        with self._lock:
            self.model_dir.mkdir(parents=True, exist_ok=True)
            if not model_path.is_file() or model_path.stat().st_size < 1024:
                self._download_asset(
                    f"{self.VOICE_ROOT}/{remote_dir}/{file_stem}.onnx?download=true",
                    model_path,
                )
            if not config_path.is_file() or config_path.stat().st_size < 100:
                self._download_asset(
                    f"{self.VOICE_ROOT}/{remote_dir}/{file_stem}.onnx.json?download=true",
                    config_path,
                    max_bytes=2 * 1024 * 1024,
                )
            if self.voice_status(selected) != "installed":
                raise TTSError("Скачанный голос Piper не прошёл проверку файлов.")
        logger.info("tts_voice_installed voice=%s path=%s", selected, model_path)
        return model_path

    @staticmethod
    def _download_asset(url: str, target: Path, max_bytes: int = MAX_VOICE_FILE_BYTES) -> None:
        temporary = target.with_name(target.name + ".part")
        temporary.unlink(missing_ok=True)
        written = 0
        try:
            with requests.get(url, stream=True, timeout=(10, 60), allow_redirects=True) as response:
                final_url = str(getattr(response, "url", url))
                if not final_url.lower().startswith("https://"):
                    raise TTSError("Загрузка голоса остановлена: сервер перенаправил на небезопасный URL.")
                response.raise_for_status()
                declared_size = response.headers.get("Content-Length")
                if declared_size:
                    try:
                        if int(declared_size) > max_bytes:
                            raise TTSError("Файл голоса превышает допустимый размер.")
                    except ValueError:
                        pass
                with temporary.open("wb") as output:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if not chunk:
                            continue
                        written += len(chunk)
                        if written > max_bytes:
                            raise TTSError("Файл голоса превышает допустимый размер.")
                        output.write(chunk)
                    output.flush()
                    os.fsync(output.fileno())
            if written < 16:
                raise TTSError("Сервер вернул пустой или слишком маленький файл голоса.")
            os.replace(temporary, target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        text = prepare_speech_text(text)
        if not text:
            raise TTSError("Нет текста для озвучивания.")
        with self._lock:
            if self.voice_status(self.voice_name) != "installed":
                raise TTSVoiceNotInstalledError(
                    "Голос TTS не установлен. Открой настройки и скачай выбранный голос."
                )
            if self._voice is None or self._loaded_voice_name != self.voice_name:
                try:
                    from piper import PiperVoice

                    model_path, _config_path = self.paths_for()
                    self._voice = PiperVoice.load(model_path)
                    self._loaded_voice_name = self.voice_name
                except Exception as exc:
                    logger.exception("tts_piper_model_load_failed voice=%s", self.voice_name)
                    raise TTSError(
                        "Не удалось загрузить Piper. Проверь установку зависимостей TTS."
                    ) from exc

            try:
                from piper import SynthesisConfig

                synthesis_config = SynthesisConfig(
                    length_scale=1.0 / self.speed,
                    volume=self.volume,
                )
                audio_chunks = list(self._voice.synthesize(text, syn_config=synthesis_config))
                if not audio_chunks:
                    raise TTSError("Piper не вернул аудиоданные.")
                arrays = [
                    np.asarray(chunk.audio_float_array, dtype=np.float32).reshape(-1)
                    for chunk in audio_chunks
                    if np.asarray(chunk.audio_float_array).size
                ]
                if not arrays:
                    raise TTSError("Piper создал пустой аудиофрагмент.")
                audio = np.concatenate(arrays).astype(np.float32, copy=False)
                sample_rate = int(audio_chunks[0].sample_rate)
            except TTSError:
                raise
            except Exception as exc:
                logger.exception("tts_piper_synthesis_failed voice=%s", self.voice_name)
                raise TTSError(f"Ошибка синтеза речи Piper: {exc}") from exc
        return audio, sample_rate


class TTSService:
    """Event-driven speech queue shared by assistant answers and rofl lines."""

    TEST_PHRASE = "Привет. Это проверка синтеза речи Джарвиса."

    def __init__(
        self,
        event_bus,
        config,
        backend: PiperTTSBackend | None = None,
        player: AudioPlayer | None = None,
        queue_capacity: int = 16,
    ):
        self.events = event_bus
        self._backend = backend or PiperTTSBackend()
        self._player = player or SoundDevicePlayer()
        self._queue: queue.Queue[tuple[str, str, bool] | None] = queue.Queue(
            maxsize=max(1, int(queue_capacity))
        )
        self._lock = threading.RLock()
        self._cancel_current = threading.Event()
        self._shutdown = threading.Event()
        self._active = False
        self._enabled = False
        self.apply_config(config)
        if self.events is not None:
            self.events.subscribe("speech.requested", self._on_speech_requested)
        self._worker = threading.Thread(
            target=self._worker_loop,
            name="jarvis-tts-worker",
            daemon=True,
        )
        self._worker.start()
        logger.info("tts_service_created enabled=%s voice=%s", self._enabled, self._backend.voice_name)

    @staticmethod
    def _as_config(config) -> dict:
        if hasattr(config, "data"):
            config = config.data
        return config if isinstance(config, dict) else {}

    def _emit(self, event: str, *args) -> None:
        if self.events is not None:
            self.events.emit(event, *args)

    @property
    def enabled(self) -> bool:
        with self._lock:
            return self._enabled

    def apply_config(self, config) -> None:
        data = self._as_config(config)
        tts_config = data.get("tts", {})
        enabled = bool(tts_config.get("enabled", False))
        self._backend.configure(
            voice_name=tts_config.get("voice", DEFAULT_TTS_VOICE),
            speed=tts_config.get("speed", DEFAULT_TTS_SPEED),
            volume=tts_config.get("volume", DEFAULT_TTS_VOLUME),
        )
        with self._lock:
            was_enabled = self._enabled
            self._enabled = enabled
        if was_enabled and not enabled:
            self.stop()
        installed = self._backend.voice_status() == "installed"
        self._emit(
            "tts.state_changed",
            "ready" if installed else "disabled" if not enabled else "missing",
            "Голос TTS установлен." if installed
            else "TTS выключен." if not enabled
            else "Голос TTS ещё не скачан.",
        )

    def voice_status(self, voice_name: str | None = None) -> str:
        return self._backend.voice_status(voice_name)

    def ensure_voice(self, voice_name: str | None = None) -> Path:
        selected = voice_name or self._backend.voice_name
        self._emit("tts.state_changed", "downloading", f"Скачиваю голос {selected}…")
        try:
            result = self._backend.ensure_voice(selected)
            status = "ready" if self._backend.voice_status(selected) == "installed" else "missing"
            self._emit("tts.state_changed", status, "Голос TTS скачан и проверен.")
            return result
        except Exception as exc:
            logger.exception("tts_voice_download_failed voice=%s", selected)
            self._emit("tts.state_changed", "error", str(exc))
            raise

    def configure_preview(self, voice_name: str, speed: float) -> None:
        """Apply unsaved UI choices for the voice test without persisting settings."""
        self._backend.configure(
            voice_name=voice_name,
            speed=speed,
            volume=self._backend.volume,
        )

    def _on_speech_requested(self, text: str, source: str = "assistant") -> None:
        self.speak(text, source=source, force=False)

    def speak(self, text: str, source: str = "assistant", force: bool = False) -> bool:
        text = prepare_speech_text(text)
        if not text:
            return False
        with self._lock:
            if self._shutdown.is_set() or (not self._enabled and not force):
                return False
        try:
            self._queue.put_nowait((text, str(source or "assistant"), bool(force)))
            return True
        except queue.Full:
            logger.warning("tts_queue_full source=%s chars=%d", source, len(text))
            self._emit("tts.state_changed", "error", "Очередь озвучивания заполнена, фраза пропущена.")
            return False

    def test(self, voice_name: str | None = None, speed: float | None = None) -> bool:
        selected = voice_name or self._backend.voice_name
        self._backend.configure(
            voice_name=selected,
            speed=self._backend.speed if speed is None else speed,
            volume=self._backend.volume,
        )
        return self.speak(self.TEST_PHRASE, source="settings", force=True)

    def stop(self) -> None:
        self._cancel_current.set()
        self._clear_queue()
        try:
            self._player.stop()
        except Exception:
            logger.debug("tts_player_stop_failed", exc_info=True)
        with self._lock:
            active = self._active
        if not active:
            self._emit("tts.state_changed", "idle", "Озвучивание остановлено.")

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                return

    def _worker_loop(self) -> None:
        while not self._shutdown.is_set():
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue
            if item is None:
                self._queue.task_done()
                return
            text, source, force = item
            try:
                with self._lock:
                    enabled = self._enabled
                    self._active = True
                if not force and not enabled:
                    continue

                self._cancel_current.clear()
                chunks = split_speech_text(text)
                if not chunks:
                    continue
                self._emit("tts.state_changed", "synthesizing", "Подготавливаю озвучку…")
                for index, speech_chunk in enumerate(chunks):
                    if self._cancel_current.is_set() or self._shutdown.is_set():
                        break
                    audio, sample_rate = self._backend.synthesize(speech_chunk)
                    if self._cancel_current.is_set() or self._shutdown.is_set():
                        break
                    self._emit("tts.state_changed", "speaking", "Озвучиваю ответ…")
                    self._player.play(audio, sample_rate)
                    if index + 1 < len(chunks) and not self._cancel_current.is_set():
                        self._emit("tts.state_changed", "synthesizing", "Подготавливаю следующую фразу…")
                if self._cancel_current.is_set() or self._shutdown.is_set():
                    self._emit("tts.state_changed", "idle", "Озвучивание остановлено.")
                else:
                    logger.info("tts_playback_complete source=%s chars=%d", source, len(text))
                    self._emit("tts.state_changed", "idle", "Озвучивание завершено.")
            except Exception as exc:
                logger.exception("tts_request_failed source=%s", source)
                self._emit("tts.state_changed", "error", str(exc))
            finally:
                with self._lock:
                    self._active = False
                self._queue.task_done()

    def close(self) -> None:
        if self._shutdown.is_set():
            return
        self._shutdown.set()
        self._cancel_current.set()
        if self.events is not None:
            self.events.unsubscribe("speech.requested", self._on_speech_requested)
        self._clear_queue()
        try:
            self._player.stop()
        except Exception:
            logger.debug("tts_player_stop_failed", exc_info=True)
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            pass
        worker = getattr(self, "_worker", None)
        if worker is not None and worker.is_alive():
            worker.join(timeout=2.0)
