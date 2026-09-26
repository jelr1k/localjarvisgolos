from __future__ import annotations

import json
import logging
import time
from collections import deque
from threading import Event

from chat.conversation import Conversation
from core.alias_manager import AliasManager
from core.task_runner import TaskRunner
from llm.request import ChatRequest
from services.command_router import CommandRouter
from tools.executor import ToolExecutor
from tools.registry import ollama_tools


logger = logging.getLogger("jarvis.chat")


class ChatService:
    """Framework-independent chat/application service.

    Presentation layers subscribe to EventBus events instead of being called
    directly by this service.
    """

    def __init__(self, provider, config, ollama_manager=None, alias_manager: AliasManager | None = None,
                 permission_manager=None, event_bus=None, task_runner: TaskRunner | None = None):
        self.provider = provider
        self.config = config
        self.ollama_manager = ollama_manager
        self.alias_manager = alias_manager or AliasManager()
        self.permission_manager = permission_manager
        self.events = event_bus
        self.tasks = task_runner or TaskRunner(max_workers=4)
        self.conversation = Conversation()
        self.router = CommandRouter(config, ollama_manager, self.alias_manager)
        self._current_answer = ""
        self._pending_messages = deque()
        self._pending_confirmation = None
        self._generation_future = None
        self._ollama_task_running = False
        self._ui_actions = {}
        logger.info("chat_service_created model=%s", self.config.get("model"))

    def _emit(self, event: str, *args):
        if self.events is not None:
            self.events.emit(event, *args)

    def set_ui_actions(self, actions: dict | None) -> None:
        self._ui_actions = dict(actions or {})
        self.router.set_ui_actions(self._ui_actions)

    def refresh_tools(self):
        logger.info("refresh_tools")
        self.router = CommandRouter(self.config, self.ollama_manager, self.alias_manager)
        self.router.set_ui_actions(self._ui_actions)

    def send(self, text, thinking=False):
        text = str(text).strip()
        if not text:
            return

        if self._pending_confirmation is not None:
            if self._handle_pending_confirmation(text):
                return
            direct = "У меня есть ожидающее подтверждение. Ответь «да» или «нет»."
            self.conversation.add("assistant", direct)
            self._emit("chat.direct_response", direct)
            return

        if self._generation_future is not None and not self._generation_future.done():
            self._pending_messages.append((text, bool(thinking)))
            logger.info("message_queued queue_size=%d text=%r", len(self._pending_messages), text)
            return

        self._process_message(text, bool(thinking))

    def _process_message(self, text: str, thinking: bool = False):
        logger.info("user_message text=%r", text)
        self.conversation.add("user", text)

        if self.router:
            if self._is_background_router_command(text):
                self._start_background_router(text)
                return
            try:
                direct = self.router.route(text, self._confirm_direct, self._confirm_alias)
            except Exception as exc:
                logger.exception("router_failed text=%r", text)
                direct = f"Не удалось выполнить прямую команду: {exc}"
            if direct is not None:
                self.conversation.add("assistant", direct)
                self._emit("chat.direct_response", direct)
                return

        if self.config.get("router_only_mode", False):
            direct = "Роутер не распознал команду. LLM отключён в тестовом режиме."
            self.conversation.add("assistant", direct)
            self._emit("chat.direct_response", direct)
            return

        self._current_answer = ""
        tools_for_message = self.router.tools_for_message(text) if self.router else set()
        request = ChatRequest(
            model=self.config.get("model"),
            messages=self.conversation.as_ollama_messages(),
            thinking=bool(thinking),
            temperature=float(self.config.get("temperature")),
            context_length=int(self.config.get("context_length")),
            max_tokens=int(self.config.get("max_tokens")),
            tools=ollama_tools(tools_for_message),
        )
        logger.info("llm_request_prepared model=%s tools=%s", request.model, sorted(tools_for_message))
        self._generation_future = self.tasks.submit(self._run_generation, request)
        self._generation_future.add_done_callback(self._generation_done)
        self._emit("chat.generation_started", request)

    def _run_generation(self, request):
        started = time.perf_counter()
        allowed_tools = {
            tool.get("function", {}).get("name")
            for tool in request.tools or []
            if tool.get("function", {}).get("name")
        }
        executor = ToolExecutor(
            self.config,
            enabled_tools=allowed_tools,
            alias_manager=self.alias_manager,
            permission_manager=self.permission_manager,
        )
        messages = list(request.messages)
        stats = None

        try:
            if self.ollama_manager is not None and not self.ollama_manager.is_running():
                self.ollama_manager.start()

            for round_number in range(1, 6):
                request.messages = messages
                tool_calls = []
                assistant_message = None

                for item in self.provider.stream_chat(request):
                    if not item.done:
                        if item.tool_calls:
                            tool_calls.extend(item.tool_calls)
                            assistant_message = item.raw.get("message") or assistant_message
                        if item.text:
                            self._current_answer += item.text
                        self._emit("chat.chunk", item)
                        continue

                    stats = item.stats
                    if item.raw.get("message"):
                        assistant_message = item.raw["message"]

                if not tool_calls:
                    if self._current_answer.strip():
                        self.conversation.add("assistant", self._current_answer)
                    return stats

                assistant_message = dict(assistant_message or {"role": "assistant", "content": ""})
                assistant_message["role"] = "assistant"
                assistant_message["tool_calls"] = tool_calls
                messages.append(assistant_message)

                for tool_call in tool_calls:
                    function = tool_call.get("function") or {}
                    tool_name = function.get("name")
                    arguments = self._normalize_arguments(function.get("arguments", {}))
                    if not tool_name:
                        continue
                    result = executor.execute(tool_name, arguments, self._confirm_tool)
                    messages.append({"role": "tool", "content": json.dumps(result, ensure_ascii=False)})

            raise RuntimeError("Слишком много последовательных вызовов инструментов.")
        except Exception as exc:
            logger.exception("generation_failed elapsed=%.4fs error=%s", time.perf_counter() - started, exc)
            raise

    @staticmethod
    def _normalize_arguments(arguments):
        if isinstance(arguments, dict):
            return arguments
        if isinstance(arguments, str):
            try:
                return json.loads(arguments)
            except json.JSONDecodeError:
                return {}
        return {}

    def _generation_done(self, future):
        try:
            stats = future.result()
        except Exception as exc:
            self._emit("chat.error", str(exc))
        else:
            self._emit("chat.generation_finished", stats)
        finally:
            self._generation_future = None
            if self._pending_messages:
                next_text, next_thinking = self._pending_messages.popleft()
                self._process_message(next_text, next_thinking)

    def _handle_pending_confirmation(self, text):
        confirmation = self._parse_confirmation(text)
        if confirmation is None:
            return False

        pending = self._pending_confirmation
        self._pending_confirmation = None

        if pending.get("mode") == "llm":
            pending["result"][0] = confirmation
            pending["event"].set()
            direct = "Подтверждение получено." if confirmation else "Действие отменено."
        else:
            direct = (
                self.router.execute_confirmed(pending["tool_name"], pending["arguments"])
                if confirmation else "Действие отменено."
            )
        self.conversation.add("assistant", direct)
        self._emit("chat.direct_response", direct)
        return True

    def _confirm_direct(self, tool_name, arguments):
        self._pending_confirmation = {
            "mode": "router",
            "tool_name": tool_name,
            "arguments": dict(arguments),
        }
        self._emit("chat.confirmation_requested", tool_name, dict(arguments))
        return None

    def _confirm_tool(self, tool_name, arguments):
        event = Event()
        result = [False]
        self._pending_confirmation = {
            "mode": "llm",
            "tool_name": tool_name,
            "arguments": dict(arguments),
            "event": event,
            "result": result,
        }
        self._emit("chat.tool_confirmation_requested", tool_name, arguments, (event, result))
        event.wait()
        return result[0]

    @staticmethod
    def _confirm_alias(query, target, category):
        return False

    @staticmethod
    def _parse_confirmation(text):
        normalized = " ".join(str(text).casefold().replace(".", " ").split())
        if normalized in {"да", "ага", "подтверждаю", "подтвердить", "выполняй", "делай", "ок", "ok"}:
            return True
        if normalized in {"нет", "не", "отмена", "отменить", "отменяй", "не надо"}:
            return False
        return None

    def _is_background_router_command(self, text):
        normalized = self.router._normalize_command_text(text).casefold()
        commands = set()
        for command_id in ("model_unload", "ollama_start", "ollama_stop"):
            commands.update(item.casefold() for item in self.router._definition_display(command_id))
        return normalized in commands

    def _start_background_router(self, text):
        if self._ollama_task_running:
            direct = "Операция с Ollama уже выполняется."
            self.conversation.add("assistant", direct)
            self._emit("chat.direct_response", direct)
            return

        self._ollama_task_running = True
        self._emit("chat.direct_response", "Выполняю операцию с Ollama в фоне…")
        future = self.tasks.submit(
            lambda: self.router.route(text, self._confirm_direct, self._confirm_alias)
        )
        future.add_done_callback(self._background_router_done)

    def _background_router_done(self, future):
        self._ollama_task_running = False
        try:
            result = future.result()
            direct = str(result)
        except Exception as exc:
            direct = f"Не удалось выполнить команду: {exc}"
        self.conversation.add("assistant", direct)
        self._emit("chat.direct_response", direct)

    def _on_chunk(self, chunk):
        if chunk.text:
            self._current_answer += chunk.text

    def add_assistant_message(self, text):
        if text and str(text).strip():
            self.conversation.add("assistant", text)

    def shutdown(self):
        self._pending_messages.clear()
        self._pending_confirmation = None
