from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.alias_manager import AliasError, AliasManager


class AliasManagerTests(unittest.TestCase):
    def make_manager(self, directory: str):
        return AliasManager(Path(directory) / "aliases.json")

    def test_aliases_persist_and_resolve(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "aliases.json"
            manager = AliasManager(path)
            manager.set_aliases("applications", "Discord", ["discord", "дискорд", "дс", "DS"])

            reloaded = AliasManager(path)
            self.assertEqual(reloaded.resolve("applications", "ДИСкорД")["target"], "Discord")
            self.assertEqual(reloaded.resolve("applications", "дс")["target"], "Discord")

    def test_alias_collision_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.make_manager(directory)
            manager.set_aliases("applications", "Discord", ["дс"])
            with self.assertRaises(AliasError):
                manager.set_aliases("applications", "Steam", ["Дс"])

    def test_default_application_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.make_manager(directory)
            self.assertEqual(
                manager.default_aliases("applications", "Prism Launcher"),
                ["Prism Launcher", "Prism"],
            )

    def test_fuzzy_suggestion_does_not_modify_storage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "aliases.json"
            manager = AliasManager(path)
            manager.set_aliases("applications", "Prism Launcher", ["prism"])

            suggestions = manager.suggest("applications", "присм")
            self.assertTrue(suggestions)
            self.assertEqual(suggestions[0]["target"], "Prism Launcher")

            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data["applications"]["Prism Launcher"]["aliases"], ["prism"])

    def test_tool_argument_alias_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = self.make_manager(directory)
            manager.set_aliases("applications", "Discord", ["дс"])
            manager.set_aliases("files", "notes/todo.txt", ["задачи"])

            args, result = manager.resolve_tool_arguments("launch_application", {"target": "Дс"})
            self.assertIsNone(result)
            self.assertEqual(args["target"], "Discord")

            args, result = manager.resolve_tool_arguments("read_file", {"path": "Задачи"})
            self.assertIsNone(result)
            self.assertEqual(args["path"], "notes/todo.txt")


if __name__ == "__main__":
    unittest.main()
