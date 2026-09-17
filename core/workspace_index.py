from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceEntry:
    path: Path
    relative_path: str
    name: str
    stem: str
    suffix: str
    is_dir: bool


class WorkspaceIndex:
    """Snapshot of real objects currently present in the Jarvis Workspace."""

    def __init__(self, workspace: Path):
        self.workspace = Path(workspace).resolve()
        self._entries: list[WorkspaceEntry] = []
        self.refresh()

    def refresh(self) -> list[WorkspaceEntry]:
        self._entries = []
        if not self.workspace.is_dir():
            return []
        for path in self.workspace.rglob("*"):
            try:
                resolved = path.resolve()
                resolved.relative_to(self.workspace)
            except (OSError, ValueError):
                continue
            if not path.exists():
                continue
            self._entries.append(
                WorkspaceEntry(
                    path=resolved,
                    relative_path=path.relative_to(self.workspace).as_posix(),
                    name=path.name,
                    stem=path.stem,
                    suffix=path.suffix,
                    is_dir=path.is_dir(),
                )
            )
        self._entries.sort(key=lambda entry: entry.relative_path.casefold())
        return list(self._entries)

    def entries(self, *, include_dirs: bool = True) -> list[WorkspaceEntry]:
        if include_dirs:
            return list(self._entries)
        return [entry for entry in self._entries if not entry.is_dir]

    def find_name(self, query: str) -> list[WorkspaceEntry]:
        normalized = str(query).strip().casefold()
        if not normalized:
            return []
        return [
            entry for entry in self._entries
            if entry.name.casefold() == normalized
            or entry.stem.casefold() == normalized
            or entry.relative_path.casefold() == normalized
        ]
