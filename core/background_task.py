from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Signal


class BackgroundTaskSignals(QObject):
    finished = Signal(object)


class BackgroundTask(QRunnable):
    """Runs a blocking callable outside the GUI thread and returns its result."""

    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = BackgroundTaskSignals()

    def run(self):
        try:
            result = self.function()
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
        self.signals.finished.emit(result)
