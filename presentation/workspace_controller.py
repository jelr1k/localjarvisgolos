from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import QObject
from core.workspace_view_model import WorkspaceViewModel


class WorkspaceController(QObject):
    def __init__(self, workspace: Path, alias_manager):
        super().__init__()
        self.model = WorkspaceViewModel(workspace, alias_manager)

    @property
    def workspace(self):
        return self.model.index.workspace

    def refresh(self):
        return self.model.refresh()

    def add_file(self, source):
        return self.model.add_file(source)

    def set_aliases(self, entry, aliases):
        return self.model.set_aliases(entry, aliases)
