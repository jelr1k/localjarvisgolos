from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class DependencyController(QObject):
    progress = Signal(str, int, int, float)
    state_changed = Signal(str, str)
    finished = Signal(str, bool, str)

    def __init__(self, manager, event_bus):
        super().__init__()
        self.manager = manager
        self._events = event_bus
        event_bus.subscribe("dependency.progress", self.progress.emit)
        event_bus.subscribe("dependency.state_changed", self.state_changed.emit)
        event_bus.subscribe("dependency.finished", self.finished.emit)

    def whisper_status(self, model_name):
        return self.manager.whisper_status(model_name)

    def ensure_whisper_model(self, model_name):
        return self.manager.ensure_whisper_model(model_name)

    def whisper_download_size(self, model_name):
        return self.manager.whisper_download_size(model_name)

    def cancel(self):
        self.manager.cancel()
