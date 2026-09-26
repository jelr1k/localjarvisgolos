from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class WakeWordController(QObject):
    detected = Signal(str)
    recognized = Signal(str)
    listening_changed = Signal(bool)
    status = Signal(str)
    error = Signal(str)

    def __init__(self, service, event_bus):
        super().__init__()
        self.service = service
        self._events = event_bus
        event_bus.subscribe("wake_word.detected", self.detected.emit)
        event_bus.subscribe("wake_word.recognized", self.recognized.emit)
        event_bus.subscribe("wake_word.listening_changed", self.listening_changed.emit)
        event_bus.subscribe("wake_word.status", self.status.emit)
        event_bus.subscribe("wake_word.error", self.error.emit)

    def start(self):
        self.service.start()

    def stop(self):
        self.service.stop()

    def restart(self):
        self.service.restart()

    def apply_config(self, config):
        self.service.apply_config(config)

    def close(self):
        self.service.close()

    def is_running(self):
        return self.service.is_running()
