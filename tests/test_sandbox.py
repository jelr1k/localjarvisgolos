from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from security.sandbox import SandboxError, is_inside_sandbox, resolve_inside_sandbox


class SandboxTests(unittest.TestCase):
    def test_relative_path_inside_root_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch("security.sandbox.WORKSPACE_DIR", root):
                self.assertTrue(is_inside_sandbox("folder/file.txt"))
                self.assertEqual(resolve_inside_sandbox("folder/file.txt"), root / "folder" / "file.txt")

    def test_parent_escape_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            with patch("security.sandbox.WORKSPACE_DIR", root):
                with self.assertRaises(SandboxError):
                    resolve_inside_sandbox("../secret.txt", allow_nonexistent=True)

    def test_absolute_other_drive_or_root_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            outside = root.parent / "outside-jarvis.txt"
            with patch("security.sandbox.WORKSPACE_DIR", root):
                self.assertFalse(is_inside_sandbox(outside, allow_nonexistent=True))

    def test_symlink_outside_is_blocked_when_supported(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "workspace"
            outside = base / "outside"
            root.mkdir()
            outside.mkdir()
            target = outside / "secret.txt"
            target.write_text("secret", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("Создание symlink недоступно")
            with patch("security.sandbox.WORKSPACE_DIR", root):
                self.assertFalse(is_inside_sandbox(link, allow_nonexistent=False))


if __name__ == "__main__":
    unittest.main()
