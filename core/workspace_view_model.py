from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.alias_manager import AliasManager
from core.workspace_index import WorkspaceEntry, WorkspaceIndex


@dataclass(frozen=True)
class WorkspaceObject:
    entry: WorkspaceEntry
    automatic_aliases: tuple[str, ...]
    user_aliases: tuple[str, ...]


class WorkspaceViewModel:
    """Presentation model for the Workspace UI.

    It deliberately reuses WorkspaceIndex and AliasManager instead of
    maintaining a second filesystem or alias scan.
    """

    def __init__(self, workspace: Path, alias_manager: AliasManager | None = None):
        self.index = WorkspaceIndex(workspace)
        self.alias_manager = alias_manager or AliasManager()

    def refresh(self) -> list[WorkspaceObject]:
        self.index.refresh()
        result: list[WorkspaceObject] = []
        for entry in self.index.entries():
            automatic = tuple(dict.fromkeys(self.alias_manager.automatic_aliases(entry.category, entry.name)))
            user = tuple(self.alias_manager.get_aliases(entry.category, entry.name))
            if entry.relative_path != entry.name:
                user = tuple(dict.fromkeys((*user, *self.alias_manager.get_aliases(entry.category, entry.relative_path))))
            result.append(WorkspaceObject(entry, automatic, user))
        return result

    def set_aliases(self, entry: WorkspaceEntry, aliases: list[str]) -> None:
        target = entry.name
        self.alias_manager.set_aliases(entry.category, target, aliases)

    def remove_object_aliases(self, entry: WorkspaceEntry) -> None:
        self.alias_manager.remove_object(entry.category, entry.name)
