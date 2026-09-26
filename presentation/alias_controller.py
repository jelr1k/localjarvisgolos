from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from core.alias_manager import AliasError


class AliasController(QObject):
    changed = Signal()

    def __init__(self, manager):
        super().__init__()
        self._manager = manager

    def list_objects(self):
        return self._manager.list_objects()

    def get_aliases(self, category, target):
        return self._manager.get_aliases(category, target)

    def default_aliases(self, category, target):
        return self._manager.default_aliases(category, target)

    def set_aliases(self, category, target, aliases):
        result = self._manager.set_aliases(category, target, aliases)
        self.changed.emit()
        return result

    def remove_object(self, category, target):
        result = self._manager.remove_object(category, target)
        self.changed.emit()
        return result

    @staticmethod
    def alias_error_type():
        return AliasError
