from __future__ import annotations

from concurrent.futures import Future
from unittest.mock import Mock, patch

import pytest

from services.chat_service import ChatService
from llm.request import ChatRequest
from llm.response import GenerationStats, StreamChunk
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

    router._route_extended_tools = Mock(return_value=None)
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
    router._route_extended_tools = Mock(return_value=None)
    router._resolve_action = Mock(return_value=("launch", "Steam"))
    router._resolve_target = Mock(return_value=("Steam.exe", None))

    assert router.route("открой Steam") == "Steam уже запущен."
    assert executor.execute.call_count == 1
    assert executor.execute.call_args.args[0] == "get_process_status"


def test_router_close_generic_target_requests_clarification(tmp_path):
    router = make_router(tmp_path)
    router._route_extended_tools = Mock(return_value=None)
    router._resolve_action = Mock(return_value=("close", "приложение"))
    assert router.route("закрой приложение") == "Какое приложение закрыть?"


def test_chat_service_router_exception_becomes_direct_error():
    service = make_service()
    service.router.route = Mock(side_effect=RuntimeError("router boom"))

    service.send("тест")

    assert service.conversation.messages[-1].content == "Не удалось выполнить прямую команду: router boom"
    assert not service.tasks.submitted


def test_chat_service_runs_llm_generation_and_stores_final_answer():
    provider = Mock()
    provider.stream_chat.return_value = iter([
        StreamChunk(text="Привет", done=False),
        StreamChunk(done=True, stats=GenerationStats(model="qwen")),
    ])
    service = ChatService(
        provider,
        {
            "model": "qwen",
            "temperature": 0.7,
            "context_length": 4096,
            "max_tokens": 128,
            "tools": {},
            "router_only_mode": False,
        },
        task_runner=ManualRunner(),
    )
    service.router.tools_for_message = Mock(return_value=set())

    service._run_generation(ChatRequest(
        model="qwen",
        messages=[],
        thinking=False,
        temperature=0.7,
        context_length=4096,
        max_tokens=128,
        tools=[],
    ))

    assert service.conversation.messages[-1].role == "assistant"
    assert service.conversation.messages[-1].content == "Привет"


def test_chat_service_executes_llm_tool_call_and_returns_to_generation():
    provider = Mock()
    first = [
        StreamChunk(
            tool_calls=[{"function": {"name": "search_files", "arguments": "{\"name\": \"report.txt\"}"}}],
            raw={"message": {"role": "assistant", "content": ""}},
        ),
        StreamChunk(done=True, stats=GenerationStats(model="qwen")),
    ]
    second = [
        StreamChunk(text="Нашёл файл.", done=False),
        StreamChunk(done=True, stats=GenerationStats(model="qwen")),
    ]
    provider.stream_chat.side_effect = [iter(first), iter(second)]

    service = make_service()
    request = ChatRequest(
        model="qwen",
        messages=[],
        thinking=False,
        temperature=0.7,
        context_length=4096,
        max_tokens=128,
        tools=[{"type": "function", "function": {"name": "search_files", "parameters": {}}}],
    )

    executor = Mock()
    executor.execute.return_value = {"success": True, "matches": ["report.txt"]}
    with patch("services.chat_service.ToolExecutor", return_value=executor):
        stats = service._run_generation(request)

    assert stats.model == "qwen"
    executor.execute.assert_called_once_with(
        "search_files",
        {"name": "report.txt"},
        service._confirm_tool,
    )
    assert service.conversation.messages[-1].content == "Нашёл файл."
    assert len(provider.stream_chat.call_args_list) == 2
    assert any(message["role"] == "tool" for message in provider.stream_chat.call_args_list[1].args[0].messages)


def test_chat_service_stops_after_five_tool_rounds():
    provider = Mock()
    provider.stream_chat.side_effect = lambda request: iter([
        StreamChunk(
            tool_calls=[{"function": {"name": "search_files", "arguments": {"name": "x"}}}],
            raw={"message": {"role": "assistant", "content": ""}},
        ),
        StreamChunk(done=True, stats=GenerationStats(model="qwen")),
    ])
    service = make_service()
    executor = Mock()
    executor.execute.return_value = {"success": True, "matches": []}
    request = ChatRequest(
        model="qwen",
        messages=[],
        thinking=False,
        temperature=0.7,
        context_length=4096,
        max_tokens=128,
        tools=[{"type": "function", "function": {"name": "search_files", "parameters": {}}}],
    )

    with patch("services.chat_service.ToolExecutor", return_value=executor):
        with pytest.raises(RuntimeError, match="Слишком много"):
            service._run_generation(request)

    assert provider.stream_chat.call_count == 5
    assert executor.execute.call_count == 5


def test_chat_service_generation_done_processes_one_queued_message():
    service = make_service()
    future = Future()
    service._generation_future = future
    service._pending_messages.append(("queued", True))
    service._process_message = Mock()

    future.set_result(GenerationStats(model="qwen"))
    service._generation_done(future)

    service._process_message.assert_called_once_with("queued", True)
    assert service._generation_future is None
    assert not service._pending_messages


def test_chat_service_background_router_rejects_parallel_ollama_operation():
    service = make_service()
    service._ollama_task_running = True

    service._start_background_router("запусти ollama")

    assert service.conversation.messages[-1].content == "Операция с Ollama уже выполняется."
    assert not service.tasks.submitted


def test_chat_service_handles_llm_confirmation_result():
    service = make_service()
    event = Mock()
    result = [False]
    service._pending_confirmation = {
        "mode": "llm",
        "tool_name": "delete_file",
        "arguments": {"path": "x.txt"},
        "event": event,
        "result": result,
    }

    assert service._handle_pending_confirmation("да") is True
    assert result == [True]
    event.set.assert_called_once()
    assert service.conversation.messages[-1].content == "Подтверждение получено."


def test_chat_service_generation_done_emits_error_and_clears_state():
    service = make_service()
    future = Future()
    service._generation_future = future
    seen = []
    service.events = Mock()

    future.set_exception(RuntimeError("generation boom"))
    service._generation_done(future)

    service.events.emit.assert_called_with("chat.error", "generation boom")
    assert service._generation_future is None


def test_chat_service_background_router_done_records_result_and_rofl_event():
    service = make_service()
    service.events = Mock()
    future = Future()
    service._ollama_task_running = True
    future.set_result(("запусти ollama", "готово"))

    service._background_router_done(future)

    assert service._ollama_task_running is False
    assert service.conversation.messages[-1].content == "готово"
    service.events.emit.assert_called_with("chat.direct_response", "готово")
    

def test_chat_service_background_router_done_handles_exception():
    service = make_service()
    service.events = Mock()
    future = Future()
    future.set_exception(RuntimeError("background boom"))

    service._background_router_done(future)

    assert "background boom" in service.conversation.messages[-1].content
    assert service._ollama_task_running is False
