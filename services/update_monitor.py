"""Background GitHub Release update monitor for JARVIS.

Stage 5 of the updater: periodically checks for a new release without
blocking the application or the Qt UI thread.
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

from services.update_checker import UpdateCheckError, UpdateChecker, UpdateInfo


logger = logging.getLogger("jarvis.update_monitor")


class UpdateMonitor:
    """Periodically check GitHub Releases in a dedicated daemon thread."""

    def __init__(
        self,
        checker: UpdateChecker | None = None,
        interval_seconds: float = 6 * 60 * 60,
        initial_delay_seconds: float = 30.0,
        on_result: Callable[[dict], None] | None = None,
    ):
        self._checker = checker or UpdateChecker()
        self._interval = max(1.0, float(interval_seconds))
        self._initial_delay = max(0.0, float(initial_delay_seconds))
        self._on_result = on_result
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._running = False

    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="jarvis-update-monitor",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
            thread = self._thread
            self._thread = None

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _run(self) -> None:
        try:
            if self._stop_event.wait(self._initial_delay):
                return

            while not self._stop_event.is_set():
                self._check_once()
                if self._stop_event.wait(self._interval):
                    return
        finally:
            with self._lock:
                self._running = False
                self._thread = None

    def _check_once(self) -> None:
        try:
            info = self._checker.check()
            result = {"success": True, "info": info}
            logger.info(
                "background_update_check_finished current=%s latest=%s available=%s",
                info.current_version,
                info.latest_version,
                info.update_available,
            )
        except UpdateCheckError as exc:
            result = {"success": False, "error": str(exc)}
            logger.warning("background_update_check_failed error=%s", exc)
        except Exception as exc:
            result = {
                "success": False,
                "error": "Не удалось проверить обновления: " + str(exc),
            }
            logger.exception("background_update_check_unexpected_failure")

        if self._on_result is not None:
            try:
                self._on_result(result)
            except Exception:
                logger.exception("background_update_result_handler_failed")
