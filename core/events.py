from __future__ import annotations

from collections import defaultdict
from threading import RLock
from typing import Any, Callable


class EventBus:
    """Framework-independent event bus used by backend services."""

    def __init__(self):
        self._handlers: dict[str, list[Callable[..., Any]]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event: str, handler: Callable[..., Any]) -> None:
        with self._lock:
            if handler not in self._handlers[event]:
                self._handlers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable[..., Any]) -> None:
        with self._lock:
            handlers = self._handlers.get(event, [])
            if handler in handlers:
                handlers.remove(handler)

    def emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event, ()))
        for handler in handlers:
            try:
                handler(*args, **kwargs)
            except Exception:
                import logging
                logging.getLogger("jarvis.events").exception(
                    "event_handler_failed event=%s handler=%r", event, handler
                )
