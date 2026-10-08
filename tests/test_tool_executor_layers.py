from __future__ import annotations

from unittest.mock import Mock, patch

from core.alias_manager import AliasManager
from core.events import EventBus
from tools.executor import ToolExecutor
from tools.registry import TOOLS


class Config:
    def __init__(self, enabled=None, outside=False):
        self.data = {
            "tools": {name: (name in (enabled or set())) for name in TOOLS},
            "allow_outside_workspace": outside,
        }

    def get(self, key, default=None):
        return self.data.get(key, default)


def test_executor_rejects_unknown_disabled_and_invalid_argument_tools():
    executor = ToolExecutor(Config(enabled={"search_files"}), {"search_files"}, AliasManager())

    unknown = executor.execute("not_a_tool", {})
    disabled = executor.execute("read_file", {"path": "x"})
    invalid = executor.execute("search_files", None)

    assert unknown["success"] is False
    assert disabled["success"] is False
    assert "отключён" in disabled["error"]
    assert invalid["success"] is False
    assert "объектом" in invalid["error"]


def test_executor_calls_tool_and_emits_execution_event():
    events = EventBus()
    seen = []
    events.subscribe("tool.executed", lambda *args: seen.append(args))

    executor = ToolExecutor(Config(enabled={"search_files"}), {"search_files"}, AliasManager(), event_bus=events)

    with patch.dict(TOOLS, {"search_files": {
        "function": lambda **kwargs: {"success": True, "matches": [kwargs["name"]]},
        "description": "test",
        "parameters": {},
        "requires_confirmation": False,
    }}):
        result = executor.execute("search_files", {"name": "hello"})

    assert result == {"success": True, "matches": ["hello"]}
    assert len(seen) == 1
    assert seen[0][0] == "search_files"


def test_executor_confirmation_required_can_pending_accept_or_cancel():
    config = Config(enabled={"write_file"})
    executor = ToolExecutor(config, {"write_file"}, AliasManager())

    with patch.dict(TOOLS, {"write_file": {
        "function": lambda **kwargs: {"success": True, "path": kwargs["path"]},
        "description": "test",
        "parameters": {},
        "requires_confirmation": True,
    }}):
        pending = executor.execute("write_file", {"path": "x", "content": "y"}, confirmation_callback=lambda *_: None)
        cancelled = executor.execute("write_file", {"path": "x", "content": "y"}, confirmation_callback=lambda *_: False)
        accepted = executor.execute("write_file", {"path": "x", "content": "y"}, confirmation_callback=lambda *_: True)

    assert pending["pending_confirmation"] is True
    assert cancelled["success"] is False
    assert "отменил" in cancelled["error"]
    assert accepted["success"] is True


def test_executor_requires_explicit_confirmation_callback():
    config = Config(enabled={"delete_file"})
    executor = ToolExecutor(config, {"delete_file"}, AliasManager())

    with patch.dict(TOOLS, {"delete_file": {
        "function": lambda **kwargs: {"success": True},
        "description": "test",
        "parameters": {},
        "requires_confirmation": True,
    }}):
        result = executor.execute("delete_file", {"path": "x"})

    assert result["success"] is False
    assert "требуется подтверждение" in result["error"]


def test_executor_converts_tool_type_error_to_result():
    config = Config(enabled={"search_files"})
    executor = ToolExecutor(config, {"search_files"}, AliasManager())

    with patch.dict(TOOLS, {"search_files": {
        "function": lambda **kwargs: (_ for _ in ()).throw(TypeError("bad args")),
        "description": "test",
        "parameters": {},
        "requires_confirmation": False,
    }}):
        result = executor.execute("search_files", {"name": "x"})

    assert result["success"] is False
    assert "Неверные аргументы" in result["error"]


def test_registry_ollama_tools_filters_enabled_names():
    from tools.registry import ollama_tools

    result = ollama_tools({"search_files", "read_file"})

    assert [item["function"]["name"] for item in result] == ["search_files", "read_file"]


def test_requires_confirmation_matches_registry():
    executor = ToolExecutor(Config(enabled=set(TOOLS)), set(TOOLS), AliasManager())

    assert executor.requires_confirmation("write_file") is True
    assert executor.requires_confirmation("search_files") is False
    assert executor.requires_confirmation("unknown") is False
