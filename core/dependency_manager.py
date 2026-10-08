from __future__ import annotations

import logging
import threading
from typing import Callable

from core.logging_config import log_event
from tqdm.auto import tqdm

try:
    from huggingface_hub import snapshot_download
except ImportError:  # pragma: no cover
    snapshot_download = None


logger = logging.getLogger("jarvis.dependencies")


class ModelDownloadCancelled(Exception):
    """Raised when a managed model download is cancelled."""


class _ProgressTqdm(tqdm):
    callback: Callable[[int, int, float], None] | None = None
    cancel_event: threading.Event | None = None

    def __init__(self, *args, **kwargs):
        kwargs["disable"] = False
        super().__init__(*args, **kwargs)

    def _report(self):
        if self.cancel_event is not None and self.cancel_event.is_set():
            raise ModelDownloadCancelled()
        if self.callback is not None:
            callback = type(self).callback
            if callback is not None:
                callback(
                    int(self.n or 0),
                    int(self.total or 0),
                    float(self.format_dict.get("rate") or 0.0),
                )

    def update(self, n=1):
        result = super().update(n)
        self._report()
        return result

    def update_transfer(self, n=1):
        result = super().update_transfer(n)
        self._report()
        return result


class DependencyManager:
    """Manages optional runtime resources without GUI dependencies."""

    WHISPER_REPOS = {
        "small": "Systran/faster-whisper-small",
        "medium": "Systran/faster-whisper-medium",
        "large-v3": "Systran/faster-whisper-large-v3",
    }
    WHISPER_PATTERNS = (
        "config.json", "preprocessor_config.json", "model.bin",
        "tokenizer.json", "vocabulary.*",
    )

    def __init__(self, event_bus=None):
        self.events = event_bus
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._active_model: str | None = None
        self._cancel_event = threading.Event()

    def _emit(self, event: str, *args):
        if self.events is not None:
            self.events.emit(event, *args)

    def is_managed_whisper_model(self, model_name: str) -> bool:
        return str(model_name).strip() in self.WHISPER_REPOS

    def whisper_status(self, model_name: str) -> str:
        model_name = str(model_name).strip()
        if not self.is_managed_whisper_model(model_name) or snapshot_download is None:
            return "unknown" if not self.is_managed_whisper_model(model_name) else "missing"
        try:
            snapshot_download(
                self.WHISPER_REPOS[model_name],
                allow_patterns=list(self.WHISPER_PATTERNS),
                local_files_only=True,
            )
            return "installed"
        except Exception:
            logger.debug("whisper_model_missing model=%s", model_name, exc_info=True)
            return "missing"

    def whisper_download_size(self, model_name: str) -> int:
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
        return sum(int(getattr(item, "file_size", 0) or 0) for item in files)

    def cancel(self):
        self._cancel_event.set()

    def ensure_whisper_model(self, model_name: str) -> str:
        model_name = str(model_name).strip()
        if not self.is_managed_whisper_model(model_name):
            return model_name
        if self.whisper_status(model_name) == "installed":
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

        repo = self.WHISPER_REPOS[model_name]
        self._emit("dependency.state_changed", model_name, "downloading")
        _ProgressTqdm.callback = lambda current, total, rate: self._emit(
            "dependency.progress", model_name, current, total, rate
        )
        _ProgressTqdm.cancel_event = self._cancel_event
        try:
            if snapshot_download is None:
                raise RuntimeError("huggingface_hub недоступен")
            snapshot_download(
                repo,
                allow_patterns=list(self.WHISPER_PATTERNS),
                max_workers=1,
                tqdm_class=_ProgressTqdm,
            )
            if self.whisper_status(model_name) != "installed":
                raise RuntimeError("Модель скачалась не полностью или повреждена")
            self._emit("dependency.progress", model_name, 1, 1, 0.0)
            self._emit("dependency.state_changed", model_name, "installed")
            self._emit("dependency.finished", model_name, True, "")
            log_event("dependency_download_completed", dependency="whisper", model=model_name)
            return model_name
        except ModelDownloadCancelled:
            self._emit("dependency.state_changed", model_name, "cancelled")
            self._emit("dependency.finished", model_name, False, "Загрузка отменена")
            raise
        except Exception as exc:
            logger.exception("whisper_download_failed model=%s", model_name)
            self._emit("dependency.state_changed", model_name, "error")
            self._emit("dependency.finished", model_name, False, str(exc))
            raise
        finally:
            _ProgressTqdm.callback = None
            _ProgressTqdm.cancel_event = None
            with self._condition:
                self._active_model = None
                self._condition.notify_all()


_manager: DependencyManager | None = None
_manager_lock = threading.Lock()


def get_dependency_manager(event_bus=None) -> DependencyManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = DependencyManager(event_bus)
        elif event_bus is not None:
            _manager.events = event_bus
        return _manager
