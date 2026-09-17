from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.alias_manager import AliasManager
from core.workspace_index import WorkspaceIndex


class WorkspaceIndexTests(unittest.TestCase):
    def test_index_uses_real_workspace_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "Workspace"
            workspace.mkdir()
            (workspace / "Steam.url").write_text("[InternetShortcut]\nURL=https://store.steampowered.com/", encoding="utf-8")
            (workspace / "notes.txt").write_text("hello", encoding="utf-8")

            index = WorkspaceIndex(workspace)
            manager = AliasManager(workspace / "aliases.json")

            entry, matches = index.resolve("Steam", ("applications",), manager)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.path.name, "Steam.url")
            self.assertEqual(len(matches), 1)

            entry, matches = index.resolve("стим", ("applications",), manager)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.path.name, "Steam.url")

    def test_index_refresh_finds_files_added_outside_ui(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "Workspace"
            workspace.mkdir()
            index = WorkspaceIndex(workspace)
            self.assertEqual(index.entries(), [])

            (workspace / "from_explorer.txt").write_text("x", encoding="utf-8")
            index.refresh()

            entry, matches = index.resolve("from_explorer.txt", ("files",), fuzzy=False)
            self.assertIsNotNone(entry)
            self.assertEqual(entry.path.name, "from_explorer.txt")
            self.assertEqual(matches[0].path, entry.path)

    def test_ambiguous_names_are_not_invented_or_auto_selected(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory) / "Workspace"
            workspace.mkdir()
            (workspace / "test.txt").write_text("a", encoding="utf-8")
            (workspace / "test.json").write_text("{}", encoding="utf-8")

            index = WorkspaceIndex(workspace)
            entry, matches = index.resolve("test", ("files",), fuzzy=False)

            self.assertIsNone(entry)
            self.assertEqual({item.path.name for item in matches}, {"test.txt", "test.json"})


if __name__ == "__main__":
    unittest.main()
