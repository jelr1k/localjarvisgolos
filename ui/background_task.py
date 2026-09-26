from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal


class _Signals(QObject):
    finished = Signal(object)


class BackgroundTask(QRunnable):
    """UI-only Qt adapter for running a blocking callable off the UI thread."""

    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = _Signals()

    def run(self):
        try:
            result = self.function()
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
        self.signals.finished.emit(result)
