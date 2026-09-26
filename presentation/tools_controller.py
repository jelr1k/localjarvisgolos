from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class ToolsController(QObject):
    changed = Signal()

    def __init__(self, permission_manager, tool_registry):
        super().__init__()
        self._permissions = permission_manager
        self._tools = tool_registry

    def tools(self):
        return self._tools

    def is_enabled(self, name):
        return self._permissions.is_enabled(name)

    def set_enabled(self, name, enabled):
        self._permissions.update(name, enabled)
        self.changed.emit()
