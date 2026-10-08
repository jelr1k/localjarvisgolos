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
    assert CommandRouter._reply({"success": True, "content": "hello", "path": "x.txt"}) == "Содержимое x.txt:\nhello"
    assert CommandRouter._reply({"success": True, "matches": []}) == "Ничего не найдено."
    assert CommandRouter._reply({"success": True, "matches": ["a", "b"]}) == "Найдено:\na\nb"
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


@pytest.mark.parametrize(
    ("text", "result"),
    [
        ("статус ollama", "status"),
        ("запусти ollama", "start"),
        ("останови ollama", "stop"),
    ],
)
def test_router_handles_ollama_control_commands(tmp_path, text, result):
    ollama = Mock()
    ollama.server_status.return_value = "running"
    ollama.get_loaded_models.return_value = ["qwen"]
    ollama.stop_server.return_value = {"success": True}
    router = make_router(tmp_path)
    router.ollama_manager = ollama
    
    if result == "start":
        response = router.route(text)
        assert response == "Ollama Server запущен."
        ollama.start.assert_called_once()
    elif result == "stop":
        response = router.route(text)
        assert response == "Ollama Server остановлен."
        ollama.stop_server.assert_called_once()
    else:
        response = router.route(text)
        assert response == "Ollama Server: running. Загружено моделей: 1."
        ollama.server_status.assert_called_once()
        ollama.get_loaded_models.assert_called_once()


def test_router_returns_ollama_start_error(tmp_path):
    ollama = Mock()
    ollama.start.side_effect = RuntimeError("boom")
    router = make_router(tmp_path)
    router.ollama_manager = ollama

    assert router.route("запусти ollama") == "Не удалось запустить Ollama: boom"


def test_router_pending_numeric_selection_is_forwarded_to_application_tool(tmp_path, monkeypatch):
    router = make_router(tmp_path)
    executor = Mock()
    executor.execute.return_value = {"success": True, "path": "Steam.exe"}
    monkeypatch.setattr(router, "_executor", lambda: executor)
    monkeypatch.setattr("services.command_router.applications.has_pending_launch_choices", lambda: True)

    result = router.route("9")

    assert result == "Готово: Steam.exe"
    executor.execute.assert_called_once_with("launch_application", {"target": "9"}, confirmation_callback=None)


def test_router_ui_actions_are_abstract_and_optional(tmp_path):
    router = make_router(tmp_path)
    calls = []
    router.set_ui_actions({name: (lambda name=name: calls.append(name)) for name in ("shutdown", "minimize", "maximize", "restore")})

    assert router.route("закрой себя") == "Полностью закрываю Jarvis."
    assert router.route("сверни окно") == "Сворачиваю окно."
    assert router.route("разверни окно") == "Разворачиваю окно."
    assert router.route("восстанови окно") == "Восстанавливаю обычный размер окна."
    assert calls == ["shutdown", "minimize", "maximize", "restore"]


def test_router_search_read_and_delete_actions_use_expected_targets(tmp_path, monkeypatch):
    router = make_router(tmp_path)
    executor = Mock()
    executor._is_enabled.return_value = True
    executor.execute.side_effect = [
        {"success": True, "matches": ["x.txt"]},
        {"success": True, "content": "hello"},
        {"success": True, "path": "x.txt"},
    ]
    monkeypatch.setattr(router, "_executor", lambda: executor)

    router._resolve_action = Mock(side_effect=[
        ("search", "файл x.txt"),
        ("read", "файл x.txt"),
        ("delete", "файл x.txt"),
    ])
    router._resolve_target = Mock(return_value=("x.txt", None))

    assert router.route("поиск") == "Найдено:\nx.txt"
    assert router.route("прочитай") == "Содержимое файла:\nhello"
    assert router.route("удали") == "Готово: x.txt"
    assert executor.execute.call_args_list[0].args[0] == "search_files"
    assert executor.execute.call_args_list[1].args[0] == "read_file"
    assert executor.execute.call_args_list[2].args[0] == "delete_file"


def test_router_launch_reports_already_running_without_starting_again(tmp_path, monkeypatch):
    router = make_router(tmp_path)
    executor = Mock()
    executor._is_enabled.return_value = True
    executor.execute.return_value = {"success": True, "running": True}
    monkeypatch.setattr(router, "_executor", lambda: executor)
    router._resolve_action = Mock(return_value=("launch", "Steam"))
    router._resolve_target = Mock(return_value=("Steam.exe", None))

    assert router.route("открой Steam") == "Steam уже запущен."
    assert executor.execute.call_count == 1
    assert executor.execute.call_args.args[0] == "get_process_status"


def test_router_close_generic_target_requests_clarification(tmp_path):
    router = make_router(tmp_path)
    router._resolve_action = Mock(return_value=("close", "приложение"))
    assert router.route("закрой приложение") == "Какое приложение закрыть?"
