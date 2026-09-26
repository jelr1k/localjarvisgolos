from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class ApplicationController(QObject):
    settings_applied = Signal(str, str)

    def __init__(self, application):
        super().__init__()
        self.application = application
        self._events = application.events
        self._events.subscribe("application.settings_applied", self.settings_applied.emit)

    def apply_settings(self):
        self.application.apply_settings()

    def start(self):
        self.application.start()

    def shutdown(self):
        self.application.shutdown()

    def config_value(self, key, default=None):
        return self.application.config.get(key, default)

    def close(self):
        self._events.unsubscribe("application.settings_applied", self.settings_applied.emit)
