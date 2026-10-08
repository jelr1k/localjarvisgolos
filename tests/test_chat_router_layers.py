from __future__ import annotations

from concurrent.futures import Future
from unittest.mock import Mock, patch

import pytest

from services.chat_service import ChatService
from services.command_router import CommandRouter
from tools.registry import TOOLS


def make_router(tmp_path):
    from core.alias_manager import AliasManager
    aliases = AliasManager(tmp_path / "aliases.json")
    config = {
        "tools": {name: True for name in TOOLS},
        "assistant_name": "JARVIS",
        "model": "qwen",
        "temperature": 0.7,
        "context_length": 4096,
        "max_tokens": 128,
    }
    return CommandRouter(config, Mock(), aliases)


class ManualRunner:
    def __init__(self):
        self.submitted = []

    def submit(self, function, *args, **kwargs):
        future = Future()
        self.submitted.append((future, function, args, kwargs))
        return future

    def shutdown(self, *args, **kwargs):
        pass


def test_router_reply_handles_success_content_matches_path_and_errors():
    assert CommandRouter._reply({"success": True, "content": "hello", "path": "x.txt"}) == "Содержимое x.txt:
hello"
    assert CommandRouter._reply({"success": True, "matches": []}) == "Ничего не найдено."
    assert CommandRouter._reply({"success": True, "matches": ["a", "b"]}) == "Найдено:
a
b"
    assert CommandRouter._reply({"success": True, "running": True}) == "Приложение запущено."
    assert CommandRouter._reply({"success": False, "error": "boom"}) == "Не выполнено: boom"


def test_router_command_catalog_contains_extended_definitions(tmp_path):
    catalog = make_router(tmp_path).command_catalog()
    commands = {item["name"] for item in catalog}

    assert "Открыть приложение" in commands
    assert "Создать файл" in commands
    assert "Открыть URL" in commands


def test_router_direct_file_command_uses_extended_tool(monkeypatch, tmp_path):
    router = make_router(tmp_path)
    executor = Mock()
    executor._is_enabled.return_value = True
    executor.execute.return_value = {"success": True, "path": str(tmp_path / "x.txt")}
    monkeypatch.setattr(router, "_executor", lambda: executor)

    result = router.route("создай файл x.txt")

    assert "Готово:" in result
    executor.execute.assert_called_once()
    assert executor.execute.call_args.args[0] == "create_file"


def test_router_direct_url_command_uses_open_url_tool(monkeypatch, tmp_path):
    router = make_router(tmp_path)
    executor = Mock()
    executor._is_enabled.return_value = True
    executor.execute.return_value = {"success": True}
    monkeypatch.setattr(router, "_executor", lambda: executor)

    result = router.route("открой https://example.com")

    assert result == "Готово."
    executor.execute.assert_called_once_with(
        "open_url", {"url": "https://example.com"}, confirmation_callback=None
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Да", True),
        ("подтверждаю", True),
        ("отмена", False),
        ("не надо", False),
        ("может быть", None),
    ],
)
def test_chat_confirmation_parser(text, expected):
    assert ChatService._parse_confirmation(text) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ({"a": 1}, {"a": 1}),
        ('{"a": 1}', {"a": 1}),
        ("not-json", {}),
        (None, {}),
    ],
)
def test_chat_normalizes_tool_arguments(value, expected):
    assert ChatService._normalize_arguments(value) == expected


def make_service(config=None):
    config = config or {
        "model": "qwen",
        "temperature": 0.7,
        "context_length": 4096,
        "max_tokens": 128,
        "tools": {},
        "router_only_mode": False,
    }
    service = ChatService(Mock(), config, task_runner=ManualRunner())
    return service


def test_chat_service_direct_router_response_does_not_start_llm():
    service = make_service()
    service.router.route = Mock(return_value="Готово.")
    service.send("сделай это")

    message = service.conversation.messages[-1]
    assert message.role == "assistant"
    assert message.content == "Готово."
    assert service.router.route.called
    assert not service.tasks.submitted


def test_chat_service_router_only_mode_returns_fallback_without_llm():
    service = make_service({
        "model": "qwen",
        "tools": {},
        "router_only_mode": True,
        "temperature": 0.7,
        "context_length": 4096,
        "max_tokens": 128,
    })
    service.router.route = Mock(return_value=None)

    service.send("что-то обычное")

    message = service.conversation.messages[-1]
    assert "LLM отключён" in message.content
    assert message.role == "assistant"
    assert not service.tasks.submitted


def test_chat_service_queues_message_while_generation_is_running():
    service = make_service()
    running = Future()
    service._generation_future = running

    service.send("второе сообщение")

    assert list(service._pending_messages) == [("второе сообщение", False)]
    running.cancel()
    service.shutdown()


def test_chat_service_pending_router_confirmation_executes_or_cancels():
    service = make_service()
    service.router.execute_confirmed = Mock(return_value="Выполнено.")

    service._pending_confirmation = {
        "mode": "router",
        "tool_name": "delete_file",
        "arguments": {"path": "x.txt"},
        "command_text": "удали x.txt",
    }
    service.send("да")
    service.router.execute_confirmed.assert_called_once_with("delete_file", {"path": "x.txt"})

    service._pending_confirmation = {
        "mode": "router",
        "tool_name": "delete_file",
        "arguments": {"path": "x.txt"},
        "command_text": "удали x.txt",
    }
    service.send("нет")
    assert service.conversation.messages[-1].content == "Действие отменено."
