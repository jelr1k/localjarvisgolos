from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class ChatController(QObject):
    chunk_received = Signal(object)
    generation_started = Signal(object)
    generation_finished = Signal(object)
    direct_response = Signal(str)
    error = Signal(str)
    confirmation_requested = Signal(str, object)

    def __init__(self, service, event_bus):
        super().__init__()
        self.service = service
        self._events = event_bus
        self._subscriptions = (
            ("chat.chunk", self.chunk_received.emit),
            ("chat.generation_started", self.generation_started.emit),
            ("chat.generation_finished", self.generation_finished.emit),
            ("chat.direct_response", self.direct_response.emit),
            ("chat.error", self.error.emit),
        )
        for name, handler in self._subscriptions:
            event_bus.subscribe(name, handler)
        self._confirmation_subscription = ("chat.confirmation_requested", self._confirmation)
        self._tool_confirmation_subscription = ("chat.tool_confirmation_requested", self._tool_confirmation)
        event_bus.subscribe(*self._confirmation_subscription)
        event_bus.subscribe(*self._tool_confirmation_subscription)

    def _confirmation(self, tool_name, arguments):
        self.confirmation_requested.emit(tool_name, arguments)

    def _tool_confirmation(self, tool_name, arguments, payload):
        self.confirmation_requested.emit(tool_name, arguments)

    def send(self, text, thinking=False):
        self.service.send(text, thinking)

    def refresh_tools(self):
        self.service.refresh_tools()

    def command_catalog(self):
        return self.service.router.command_catalog()

    def set_ui_actions(self, actions):
        self.service.set_ui_actions(actions)

    def shutdown(self):
        self.service.shutdown()

    def close(self):
        for name, handler in self._subscriptions:
            self._events.unsubscribe(name, handler)
        self._events.unsubscribe(*self._confirmation_subscription)
        self._events.unsubscribe(*self._tool_confirmation_subscription)
