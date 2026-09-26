from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class VoiceController(QObject):
    listening_changed = Signal(bool)
    transcribing_changed = Signal(bool)
    transcript_ready = Signal(str)
    error = Signal(str)

    def __init__(self, service, event_bus):
        super().__init__()
        self.service = service
        self._events = event_bus
        event_bus.subscribe("voice.listening_changed", self.listening_changed.emit)
        event_bus.subscribe("voice.transcribing_changed", self.transcribing_changed.emit)
        event_bus.subscribe("voice.transcript_ready", self.transcript_ready.emit)
        event_bus.subscribe("voice.error", self.error.emit)

    @property
    def is_recording(self):
        return self.service.is_recording

    def transcribing(self):
        return self.service.transcribing()

    def start(self):
        self.service.start()

    def stop(self):
        self.service.stop()

    def apply_config(self, config):
        self.service.apply_config(config)

    def close(self):
        self.service.close()
