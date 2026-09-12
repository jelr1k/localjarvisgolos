from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import files


class FileToolTests(unittest.TestCase):
    def test_delete_file_removes_real_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            target = root / "delete-me.txt"
            target.write_text("x", encoding="utf-8")
            with patch("tools.paths.TOOL_WORKSPACE", root), patch("security.sandbox.WORKSPACE_DIR", root):
                result = files.delete_file("delete-me.txt")
            self.assertTrue(result["success"])
            self.assertFalse(target.exists())

    def test_delete_file_never_reports_success_on_outside_path(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "workspace"
            root.mkdir()
            outside = base / "outside.txt"
            outside.write_text("x", encoding="utf-8")
            with patch("tools.paths.TOOL_WORKSPACE", root), patch("security.sandbox.WORKSPACE_DIR", root):
                result = files.delete_file(str(outside))
            self.assertFalse(result["success"])
            self.assertTrue(outside.exists())

    def test_ambiguous_name_is_not_auto_selected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            (root / "a").mkdir()
            (root / "b").mkdir()
            (root / "a" / "same.txt").write_text("a", encoding="utf-8")
            (root / "b" / "same.txt").write_text("b", encoding="utf-8")
            with patch("tools.paths.TOOL_WORKSPACE", root), patch("security.sandbox.WORKSPACE_DIR", root):
                result = files.delete_file("same.txt")
            self.assertFalse(result["success"])
            self.assertTrue(result.get("ambiguous"))
            self.assertEqual(len(result.get("matches", [])), 2)


if __name__ == "__main__":
    unittest.main()
