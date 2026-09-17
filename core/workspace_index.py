from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.alias_manager import AliasManager


@dataclass(frozen=True)
class WorkspaceEntry:
    path: Path
    relative_path: str
    name: str
    stem: str
    suffix: str
    is_dir: bool

    @property
    def category(self) -> str:
        if self.is_dir:
            return "folders"
        if self.suffix.casefold() in {".exe", ".bat", ".cmd", ".com", ".lnk", ".url"}:
            return "applications"
        return "files"


class WorkspaceIndex:
    """Живой индекс реального содержимого Workspace.

    Индекс намеренно не хранит отдельную базу на диске. При refresh() источник
    истины всегда сам Workspace, поэтому файлы, добавленные через Проводник,
    становятся видимыми без ручной регистрации.
    """

    _SEPARATORS = re.compile(r"[\s_.-]+")

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

    def entries(self, categories: tuple[str, ...] | None = None) -> list[WorkspaceEntry]:
        if not categories:
            return list(self._entries)
        return [entry for entry in self._entries if entry.category in categories]

    @staticmethod
    def _normalize(value: str) -> str:
        value = str(value or "").strip().casefold().replace("ё", "е")
        return " ".join(WorkspaceIndex._SEPARATORS.split(value))

    def _aliases_for(self, entry: WorkspaceEntry, alias_manager: AliasManager | None) -> list[str]:
        if alias_manager is None:
            return [entry.name, entry.stem, entry.relative_path]
        aliases = alias_manager.automatic_aliases(entry.category, entry.name)
        aliases.extend([entry.name, entry.stem, entry.relative_path])
        return list(dict.fromkeys(alias for alias in aliases if alias))

    def resolve(
        self,
        query: str,
        categories: tuple[str, ...],
        alias_manager: AliasManager | None = None,
        *,
        fuzzy: bool = True,
    ) -> tuple[WorkspaceEntry | None, list[WorkspaceEntry]]:
        """Resolve only against real Workspace objects.

        Returns (entry, matches). entry is set only for one unambiguous match.
        No synthetic candidate is ever produced.
        """
        normalized = self._normalize(query)
        if not normalized:
            return None, []

        candidates = self.entries(categories)
        exact: list[WorkspaceEntry] = []
        for entry in candidates:
            values = self._aliases_for(entry, alias_manager)
            if any(self._normalize(value) == normalized for value in values):
                exact.append(entry)

        if exact:
            unique = {entry.path: entry for entry in exact}
            matches = sorted(unique.values(), key=lambda item: item.relative_path.casefold())
            return (matches[0], matches) if len(matches) == 1 else (None, matches)

        if not fuzzy:
            return None, []

        scored: list[tuple[float, WorkspaceEntry]] = []
        for entry in candidates:
            best = max(
                difflib.SequenceMatcher(None, normalized, self._normalize(value)).ratio()
                for value in self._aliases_for(entry, alias_manager)
            )
            if best >= 0.72:
                scored.append((best, entry))

        scored.sort(key=lambda item: (-item[0], item[1].relative_path.casefold()))
        if not scored:
            return None, []

        best_score = scored[0][0]
        matches = [entry for score, entry in scored if score >= best_score - 0.06]
        if len(matches) == 1:
            return matches[0], matches
        return None, matches

    def all_files(self) -> list[WorkspaceEntry]:
        return self.entries(("files", "applications"))
