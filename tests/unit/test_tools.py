from __future__ import annotations

from unittest.mock import Mock

from core.config_manager import ConfigManager
from security.permissions import PermissionManager
from tools.executor import ToolExecutor
from tools.registry import TOOLS, ollama_tools


def test_registry_contains_only_structured_tool_definitions():
    assert TOOLS
    for name, definition in TOOLS.items():
        assert name
        assert callable(definition["function"])
        assert isinstance(definition["parameters"], dict)
        assert isinstance(definition["requires_confirmation"], bool)


def test_ollama_tools_can_be_filtered():
    names = list(TOOLS)[:2]
    result = ollama_tools(names)

    assert {item["function"]["name"] for item in result} == set(names)
    assert all(item["type"] == "function" for item in result)


def test_executor_rejects_unknown_tool():
    executor = ToolExecutor(enabled_tools=set())

    result = executor.execute("missing_tool", {})

    assert result["success"] is False
    assert "Неизвестный инструмент" in result["error"]


def test_executor_rejects_disabled_tool():
    executor = ToolExecutor(enabled_tools={"read_file"})

    result = executor.execute("write_file", {"path": "x", "content": "x"})

    assert result["success"] is False
    assert "отключён" in result["error"]


def test_executor_rejects_non_dict_arguments():
    executor = ToolExecutor(enabled_tools={"read_file"})

    result = executor.execute("read_file", [])

    assert result["success"] is False
    assert "объектом" in result["error"]


def test_executor_requires_confirmation_for_write(tmp_path):
    config = ConfigManager(tmp_path / "settings.json")
    config.data["tools"]["write_file"] = True
    permissions = PermissionManager(config)
    executor = ToolExecutor(config=config, enabled_tools={"write_file"}, permission_manager=permissions)

    result = executor.execute("write_file", {"path": "test.txt", "content": "hello"})

    assert result["success"] is False
    assert "подтверждение" in result["error"]


def test_executor_can_run_safe_mocked_tool():
    import tools.registry as registry

    original = registry.TOOLS["file_info"]["function"]
    registry.TOOLS["file_info"]["function"] = Mock(return_value={"success": True, "size": 1})
    try:
        executor = ToolExecutor(enabled_tools={"file_info"})
        result = executor.execute("file_info", {"path": "test.txt"})
        assert result == {"success": True, "size": 1}
    finally:
        registry.TOOLS["file_info"]["function"] = original
