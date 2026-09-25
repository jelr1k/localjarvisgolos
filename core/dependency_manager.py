from __future__ import annotations

import logging
import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal

from core.logging_config import log_event
from tqdm.auto import tqdm

try:
    from huggingface_hub import snapshot_download
except ImportError:  # pragma: no cover - dependency is required by faster-whisper
    snapshot_download = None


logger = logging.getLogger("jarvis.dependencies")


class ModelDownloadCancelled(Exception):
    """Raised when a managed model download is cancelled."""


class _ProgressTqdm(tqdm):
    """Bridge Hugging Face/tqdm progress into Qt signals."""

    callback: Callable[[int, int, float], None] | None = None
    cancel_event: threading.Event | None = None

    def __init__(self, *args, **kwargs):
        kwargs["disable"] = False
        super().__init__(*args, **kwargs)

    def _report(self):
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise ModelDownloadCancelled()
        if self.callback is None:
            return
        total = int(self.total or 0)
        current = int(self.n or 0)
        rate = float(self.format_dict.get("rate") or 0.0)
        self.callback(current, total, rate)

    def update(self, n=1):
        result = super().update(n)
        self._report()
        return result

    def update_transfer(self, n=1):
        result = super().update(n)
        self._report()
        return result


class DependencyManager(QObject):
    """Manages large optional runtime resources without replacing their native caches."""

    progress = Signal(str, int, int, float)
    state_changed = Signal(str, str)
    finished = Signal(str, bool, str)

    WHISPER_REPOS = {
        "small": "Systran/faster-whisper-small",
        "medium": "Systran/faster-whisper-medium",
        "large-v3": "Systran/faster-whisper-large-v3",
    }

    WHISPER_PATTERNS = (
        "config.json",
        "preprocessor_config.json",
        "model.bin",
        "tokenizer.json",
        "vocabulary.*",
    )

    def __init__(self):
        super().__init__()
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._active_model: str | None = None
        self._cancel_event = threading.Event()

    def is_managed_whisper_model(self, model_name: str) -> bool:
        return str(model_name).strip() in self.WHISPER_REPOS

    def whisper_status(self, model_name: str) -> str:
        model_name = str(model_name).strip()
        if not self.is_managed_whisper_model(model_name):
            logger.debug("Whisper model is not managed model=%s", model_name)
            return "unknown"
        if snapshot_download is None:
            logger.error("huggingface_hub is unavailable while checking model=%s", model_name)
            return "missing"
        try:
            snapshot_download(
                self.WHISPER_REPOS[model_name],
                allow_patterns=list(self.WHISPER_PATTERNS),
                local_files_only=True,
            )
            logger.debug("Whisper model cache status model=%s status=installed", model_name)
            return "installed"
        except Exception:
            logger.debug("Whisper model cache status model=%s status=missing", model_name, exc_info=True)
            return "missing"

    def whisper_download_size(self, model_name: str) -> int:
        """Return bytes that would be downloaded now, without downloading them."""
        model_name = str(model_name).strip()
        if not self.is_managed_whisper_model(model_name):
            return 0
        if snapshot_download is None:
            raise RuntimeError("huggingface_hub недоступен")
        files = snapshot_download(
            self.WHISPER_REPOS[model_name],
            allow_patterns=list(self.WHISPER_PATTERNS),
            dry_run=True,
        )
        size = sum(int(getattr(item, "file_size", 0) or 0) for item in files)
        logger.debug("Whisper download size model=%s bytes=%s", model_name, size)
        return size

    def cancel(self):
        self._cancel_event.set()

    def ensure_whisper_model(self, model_name: str) -> str:
        model_name = str(model_name).strip()
        if not self.is_managed_whisper_model(model_name):
            return model_name

        if self.whisper_status(model_name) == "installed":
            logger.debug("Whisper model already installed model=%s", model_name)
            return model_name

        with self._condition:
            while self._active_model is not None and self._active_model != model_name:
                self._condition.wait()
            if self._active_model == model_name:
                while self._active_model == model_name:
                    self._condition.wait()
                if self.whisper_status(model_name) == "installed":
                    return model_name

            self._active_model = model_name
            self._cancel_event.clear()

        logger.info("Whisper model download started model=%s repo=%s", model_name, self.WHISPER_REPOS[model_name])
        log_event("dependency_download_started", dependency="whisper", model=model_name, repo=self.WHISPER_REPOS[model_name])
        self.state_changed.emit(model_name, "downloading")
        _ProgressTqdm.callback = lambda current, total, rate: self.progress.emit(
            model_name, current, total, rate
        )
        _ProgressTqdm.cancel_event = self._cancel_event

        try:
            if snapshot_download is None:
                logger.error("Cannot download Whisper model because huggingface_hub is unavailable model=%s", model_name)
                raise RuntimeError("huggingface_hub недоступен")

            snapshot_download(
                self.WHISPER_REPOS[model_name],
                allow_patterns=list(self.WHISPER_PATTERNS),
                max_workers=1,
                tqdm_class=_ProgressTqdm,
            )

            if self.whisper_status(model_name) != "installed":
                raise RuntimeError("Модель скачалась не полностью или повреждена")

            logger.info("Whisper model download completed model=%s", model_name)
            log_event("dependency_download_completed", dependency="whisper", model=model_name)
            self.progress.emit(model_name, 1, 1, 0.0)
            self.state_changed.emit(model_name, "installed")
            self.finished.emit(model_name, True, "")
            return model_name
        except ModelDownloadCancelled:
            logger.warning("Whisper model download cancelled model=%s", model_name)
            log_event("dependency_download_cancelled", dependency="whisper", model=model_name)
            self.state_changed.emit(model_name, "cancelled")
            self.finished.emit(model_name, False, "Загрузка отменена")
            raise
        except Exception as exc:
            logger.exception("Whisper model download failed model=%s", model_name)
            log_event("dependency_download_failed", dependency="whisper", model=model_name, error=str(exc))
            self.state_changed.emit(model_name, "error")
            self.finished.emit(model_name, False, str(exc))
            raise
        finally:
            _ProgressTqdm.callback = None
            _ProgressTqdm.cancel_event = None
            with self._condition:
                self._active_model = None
                self._condition.notify_all()


_manager: DependencyManager | None = None
_manager_lock = threading.Lock()


def get_dependency_manager() -> DependencyManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = DependencyManager()
        return _manager
