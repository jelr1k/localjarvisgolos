from tools import executor as executor_module
from tools.executor import ToolExecutor


def test_unknown_tool_is_rejected():
    executor = ToolExecutor(enabled_tools=set())
    result = executor.execute("does_not_exist", {})
    assert result["success"] is False
    assert "Неизвестный инструмент" in result["error"]


def test_tool_outside_request_scope_is_rejected():
    executor = ToolExecutor(enabled_tools={"search_files"})
    result = executor.execute("read_file", {"path": "test.txt"})
    assert result["success"] is False
    assert "отключён" in result["error"]


def test_confirmation_is_required_and_can_cancel(monkeypatch):
    called = {"value": False}

    def fake_delete(path):
        called["value"] = True
        return {"success": True}

    monkeypatch.setitem(executor_module.TOOLS, "delete_file", {
        "function": fake_delete,
        "requires_confirmation": True,
    })
    executor = ToolExecutor(enabled_tools={"delete_file"})
    result = executor.execute("delete_file", {"path": "test.txt"}, lambda *_: False)

    assert result == {"success": False, "error": "Пользователь отменил действие."}
    assert called["value"] is False


def test_confirmation_allows_tool_execution(monkeypatch):
    def fake_delete(path):
        return {"success": True, "path": path}

    monkeypatch.setitem(executor_module.TOOLS, "delete_file", {
        "function": fake_delete,
        "requires_confirmation": True,
    })
    executor = ToolExecutor(enabled_tools={"delete_file"})
    result = executor.execute("delete_file", {"path": "test.txt"}, lambda *_: True)

    assert result == {"success": True, "path": "test.txt"}
