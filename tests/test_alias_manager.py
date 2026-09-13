from __future__ import annotations

import json

import pytest

from core.alias_manager import AliasError, AliasManager


def test_aliases_persist_and_resolve(tmp_path):
    path = tmp_path / "aliases.json"
    manager = AliasManager(path)
    manager.set_aliases("applications", "Discord", ["discord", "дискорд", "дс", "DS"])

    reloaded = AliasManager(path)
    assert reloaded.resolve("applications", "ДИСкорД")["target"] == "Discord"
    assert reloaded.resolve("applications", "дс")["target"] == "Discord"


def test_alias_collision_is_rejected(tmp_path):
    manager = AliasManager(tmp_path / "aliases.json")
    manager.set_aliases("applications", "Discord", ["дс"])

    with pytest.raises(AliasError):
        manager.set_aliases("applications", "Steam", ["Дс"])


def test_default_application_aliases(tmp_path):
    manager = AliasManager(tmp_path / "aliases.json")
    assert manager.default_aliases("applications", "Prism Launcher") == ["Prism Launcher", "Prism"]


def test_fuzzy_suggestion_does_not_modify_storage(tmp_path):
    path = tmp_path / "aliases.json"
    manager = AliasManager(path)
    manager.set_aliases("applications", "Prism Launcher", ["prism"])

    suggestions = manager.suggest("applications", "присм")
    assert suggestions
    assert suggestions[0]["target"] == "Prism Launcher"

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["applications"]["Prism Launcher"]["aliases"] == ["prism"]


def test_tool_argument_alias_resolution(tmp_path):
    manager = AliasManager(tmp_path / "aliases.json")
    manager.set_aliases("applications", "Discord", ["дс"])
    manager.set_aliases("files", "notes/todo.txt", ["задачи"])

    args, result = manager.resolve_tool_arguments("launch_application", {"target": "Дс"})
    assert result is None
    assert args["target"] == "Discord"

    args, result = manager.resolve_tool_arguments("read_file", {"path": "Задачи"})
    assert result is None
    assert args["path"] == "notes/todo.txt"
