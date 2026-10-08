from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.paths import add_file_to_workspace


class WorkspaceFileTests(unittest.TestCase):
    def test_add_file_to_workspace_copies_file_without_removing_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DDNet.exe"
            target = root / "workspace" / source.name
            source.write_bytes(b"test-data")
            target.parent.mkdir()

            with patch("tools.paths.prepare_tool_workspace", return_value=target.parent), \
                 patch("tools.paths.resolve_inside_sandbox", return_value=target):
                result = add_file_to_workspace(source)

            self.assertEqual(result, target.resolve())
            self.assertTrue(source.exists())
            self.assertTrue(target.exists())
            self.assertEqual(target.read_bytes(), b"test-data")


    def test_add_file_to_workspace_is_idempotent_for_existing_workspace_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            source = workspace / "Steam.lnk"
            source.write_bytes(b"shortcut")

            with patch("tools.paths.prepare_tool_workspace", return_value=workspace), \
                 patch("tools.paths.resolve_inside_sandbox", return_value=source), \
                 patch("tools.paths.TOOL_WORKSPACE", workspace):
                result = add_file_to_workspace(source)

            self.assertEqual(result, source.resolve())
            self.assertEqual(source.read_bytes(), b"shortcut")

    def test_add_file_to_workspace_rejects_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "folder"
            source.mkdir()

            with self.assertRaises(ValueError):
                add_file_to_workspace(source)

    def test_add_file_to_workspace_rejects_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "DDNet.exe"
            target = root / "workspace" / source.name
            source.write_bytes(b"new")
            target.parent.mkdir()
            target.write_bytes(b"old")

            with patch("tools.paths.prepare_tool_workspace", return_value=target.parent), \
                 patch("tools.paths.resolve_inside_sandbox", return_value=target), \
                 patch("tools.paths.shutil.copy2") as copy2:
                with self.assertRaises(FileExistsError):
                    add_file_to_workspace(source)

            copy2.assert_not_called()


if __name__ == "__main__":
    unittest.main()
