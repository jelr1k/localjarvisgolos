from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path

from .asset_manager import AudioAssetManager
from .audio_player import AudioPlayer, SoundDevicePlayer
from .engine import TTSBackend
from .metrics import TTSMetrics
from .text import prepare_speech_text, split_speech_text
from .engines.piper import DEFAULT_TTS_SPEED, DEFAULT_TTS_VOLUME, DEFAULT_TTS_VOICE, PiperTTSBackend

logger = logging.getLogger("jarvis.tts")

class TTSService:
    """Event-driven speech queue shared by assistant answers and rofl lines."""

    TEST_PHRASE = "Привет. Это проверка синтеза речи Джарвиса."

    def __init__(
        self,
        event_bus,
        config,
        backend: TTSBackend | None = None,
        player: AudioPlayer | None = None,
        queue_capacity: int = 16,
        asset_manager: AudioAssetManager | None = None,
    ):
        self.events = event_bus
        self._backend = backend or PiperTTSBackend()
        self._player = player or SoundDevicePlayer()
        self._assets = asset_manager or AudioAssetManager()
        self.metrics = TTSMetrics()
        self._queue: queue.Queue[tuple[str, str, bool, tuple[str, float, float] | None, int, str | None, Path | None] | None] = queue.Queue(
            maxsize=max(1, int(queue_capacity))
        )
        self._lock = threading.RLock()
        self._cancel_current = threading.Event()
        self._cancel_generation = 0
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
            self.metrics.record_error()
            logger.exception("tts_voice_download_failed voice=%s", selected)
            self._emit("tts.state_changed", "error", str(exc))
            raise

    def _on_speech_requested(
        self, text: str, source: str = "assistant", response_key: str | None = None
    ) -> None:
        self.speak(text, source=source, force=False, response_key=response_key)

    def speak(
        self, text: str, source: str = "assistant", force: bool = False, response_key: str | None = None
    ) -> bool:
        return self._queue_speech(text, source, force, preview_settings=None, response_key=response_key)

    def register_prepared_audio(
        self, voice_name: str, response_key: str, text: str, source_path: str | Path
    ) -> Path:
        result = self._assets.register_prepared_file(voice_name, response_key, source_path, text=text)
        logger.info("tts_prepared_audio_imported voice=%s response_key=%s", voice_name, response_key)
        self._emit("tts.state_changed", "idle", f"Готовая озвучка «{response_key}» добавлена.")
        return result

    def list_prepared_audio(self, voice_name: str | None = None) -> list[dict]:
        return self._assets.list_prepared_audio(voice_name)

    def remove_prepared_audio(self, voice_name: str, response_key: str) -> bool:
        removed = self._assets.remove_prepared_audio(voice_name, response_key)
        if removed:
            logger.info("tts_prepared_audio_removed voice=%s response_key=%s", voice_name, response_key)
        return removed

    def play_prepared_audio(self, voice_name: str, response_key: str) -> bool:
        path = self._assets.find_prepared_audio(voice_name, response_key)
        if path is None:
            return False
        try:
            with self._lock:
                if self._shutdown.is_set():
                    return False
                generation = self._cancel_generation
                self._queue.put_nowait(("", "prepared-preview", True, None, generation, response_key, path))
            return True
        except queue.Full:
            self.metrics.record_queue_rejection()
            self._emit("tts.state_changed", "error", "Очередь озвучивания заполнена, запись не добавлена.")
            return False

    def audio_stats(self) -> dict:
        prepared = self._assets.list_prepared_audio()
        cache_files = list(self._assets.cache_dir.glob("*.wav")) if self._assets.cache_dir.exists() else []
        return {
            "prepared_count": len(prepared),
            "prepared_bytes": sum(item["size_bytes"] for item in prepared),
            "cache_count": len(cache_files),
            "cache_bytes": sum(path.stat().st_size for path in cache_files if path.is_file()),
            "cache_limit_bytes": self._assets.max_cache_bytes,
            "metrics": self.metrics.snapshot().to_dict(),
        }

    def clear_audio_cache(self) -> int:
        removed = self._assets.clear_cache()
        logger.info("tts_audio_cache_cleared removed=%s", removed)
        return removed

    def _queue_speech(
        self,
        text: str,
        source: str,
        force: bool,
        preview_settings: tuple[str, float, float] | None,
        response_key: str | None = None,
        prepared_path: Path | None = None,
    ) -> bool:
        self.metrics.record_request()
        text = prepare_speech_text(text)
        if not text:
            return False
        try:
            with self._lock:
                if self._shutdown.is_set() or (not self._enabled and not force):
                    return False
                generation = self._cancel_generation
                self._queue.put_nowait(
                    (text, str(source or "assistant"), bool(force), preview_settings, generation, response_key, prepared_path)
                )
            return True
        except queue.Full:
            self.metrics.record_queue_rejection()
            logger.warning("tts_queue_full source=%s chars=%d", source, len(text))
            self._emit("tts.state_changed", "error", "Очередь озвучивания заполнена, фраза пропущена.")
            return False

    def test(
        self,
        voice_name: str | None = None,
        speed: float | None = None,
        volume: float | None = None,
    ) -> bool:
        selected = voice_name or self._backend.voice_name
        previous = (self._backend.voice_name, self._backend.speed, self._backend.volume)
        speed_value = self._backend.speed if speed is None else float(speed)
        volume_value = self._backend.volume if volume is None else float(volume)
        # Validate the preview without persisting it into the active configuration.
        self._backend.configure(selected, speed_value, volume_value)
        preview = (self._backend.voice_name, self._backend.speed, self._backend.volume)
        self._backend.configure(*previous)
        return self._queue_speech(
            self.TEST_PHRASE,
            source="settings",
            force=True,
            preview_settings=preview,
        )

    def stop(self) -> None:
        with self._lock:
            self._cancel_generation += 1
            self._cancel_current.set()
            self._clear_queue()
            active = self._active
        try:
            self._player.stop()
        except Exception:
            logger.debug("tts_player_stop_failed", exc_info=True)
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
            text, source, force, preview_settings, generation, response_key, prepared_path = item
            try:
                with self._lock:
                    if generation != self._cancel_generation:
                        continue
                    enabled = self._enabled
                    self._active = True
                    self._cancel_current.clear()
                if not force and not enabled:
                    continue
                if prepared_path is None:
                    selected_voice = preview_settings[0] if preview_settings is not None else self._backend.voice_name
                    prepared_path = (
                        self._assets.find_prepared_audio(selected_voice, response_key)
                        if response_key else None
                    )
                    if prepared_path is None:
                        prepared_path = self._assets.find_prepared_audio_for_text(selected_voice, text)
                if prepared_path is not None:
                    audio, sample_rate = self._assets.load_audio(prepared_path)
                    self._emit("tts.state_changed", "speaking", "Воспроизвожу готовую запись…")
                    self._player.play(audio, sample_rate)
                    if source != "prepared-preview":
                        self.metrics.record_prepared_hit()
                    logger.info("tts_prepared_audio_played source=%s", source)
                    self._emit("tts.state_changed", "idle", "Готовая озвучка завершена.")
                    continue
                chunks = split_speech_text(text)
                if not chunks:
                    continue
                self._emit("tts.state_changed", "synthesizing", "Подготавливаю озвучку…")
                for index, speech_chunk in enumerate(chunks):
                    if self._cancel_current.is_set() or self._shutdown.is_set():
                        break
                    previous_settings = None
                    if preview_settings is not None:
                        previous_settings = (
                            self._backend.voice_name,
                            self._backend.speed,
                            self._backend.volume,
                        )
                        self._backend.configure(*preview_settings)
                    try:
                        cache_key = AudioAssetManager.cache_key(
                            speech_chunk,
                            self._backend.voice_name,
                            engine_id=getattr(self._backend, "engine_id", "unknown"),
                            model_id=self._backend.voice_name,
                            settings={"speed": self._backend.speed, "volume": self._backend.volume},
                        )
                        audio = None
                        sample_rate = 0
                        if preview_settings is None:
                            try:
                                cached_path = self._assets.find_cached_audio(cache_key)
                                if cached_path is not None:
                                    audio, sample_rate = self._assets.load_audio(cached_path)
                                    self.metrics.record_cache_hit()
                            except Exception:
                                logger.warning("tts_cache_read_failed", exc_info=True)
                        if audio is None:
                            synthesis_started = time.perf_counter()
                            try:
                                audio, sample_rate = self._backend.synthesize(speech_chunk)
                            except Exception:
                                self.metrics.record_synthesis(time.perf_counter() - synthesis_started, success=False)
                                raise
                            else:
                                self.metrics.record_synthesis(time.perf_counter() - synthesis_started, success=True)
                            if preview_settings is None:
                                try:
                                    self._assets.save_cached_audio(cache_key, audio, sample_rate)
                                except Exception:
                                    logger.warning("tts_cache_write_failed", exc_info=True)
                    finally:
                        if previous_settings is not None:
                            try:
                                self._backend.configure(*previous_settings)
                            except Exception:
                                logger.exception("tts_preview_settings_restore_failed")
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
                self.metrics.record_error()
                logger.exception("tts_request_failed source=%s", source)
                self._emit("tts.state_changed", "error", str(exc))
            finally:
                with self._lock:
                    self._active = False
                self._queue.task_done()

    def close(self) -> None:
        if self._shutdown.is_set():
            return
        with self._lock:
            self._shutdown.set()
            self._cancel_generation += 1
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
