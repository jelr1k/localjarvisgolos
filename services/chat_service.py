from __future__ import annotations

import json
from threading import Event

from PySide6.QtCore import QObject, Signal, QThread
from PySide6.QtWidgets import QMessageBox

from chat.conversation import Conversation
from core.alias_manager import AliasManager
from llm.request import ChatRequest
from services.command_router import CommandRouter
from tools.executor import ToolExecutor
from tools.registry import TOOLS, ollama_tools


class GenerationWorker(QObject):
    chunk = Signal(object)
    finished = Signal(object)
    failed = Signal(str)
    confirmation_requested = Signal(str, object, object)

    def __init__(self, provider, request, config, alias_manager: AliasManager):
        super().__init__()
        self.provider = provider
        self.request = request
        self.config = config
        self.alias_manager = alias_manager
        self.executor = ToolExecutor(config, alias_manager=alias_manager)
        self.max_tool_rounds = 5

    def _confirm_tool(self, tool_name, arguments):
        event = Event()
        result = [False]
        self.confirmation_requested.emit(tool_name, arguments, (event, result))
        event.wait()
        return result[0]

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

    def run(self):
        try:
            messages = list(self.request.messages)
            stats = None
            for _ in range(self.max_tool_rounds):
                self.request.messages = messages
                tool_calls = []
                assistant_message = None
                for item in self.provider.stream_chat(self.request):
                    if not item.done:
                        if item.tool_calls:
                            tool_calls.extend(item.tool_calls)
                            assistant_message = item.raw.get("message") or assistant_message
                        self.chunk.emit(item)
                        continue
                    stats = item.stats
                    if item.raw.get("message"):
                        assistant_message = item.raw["message"]

                if not tool_calls:
                    self.finished.emit(stats)
                    return

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
                    result = self.executor.execute(tool_name, arguments, self._confirm_tool)
                    messages.append({
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False),
                    })

            raise RuntimeError("Слишком много последовательных вызовов инструментов.")
        except Exception as exc:
            self.failed.emit(str(exc))


class ChatService(QObject):
    chunk_received = Signal(object)
    generation_finished = Signal(object)
    direct_response = Signal(str)
    error = Signal(str)

    def __init__(self, provider, config, ollama_manager=None, alias_manager: AliasManager | None = None):
        super().__init__()
        self.provider = provider
        self.config = config
        self.ollama_manager = ollama_manager
        self.alias_manager = alias_manager or AliasManager()
        self.conversation = Conversation()
        self.router = CommandRouter(config, ollama_manager, self.alias_manager) if ollama_manager else None
        self._thread = None
        self._worker = None
        self._current_answer = ""

    def _enabled_tools(self):
        configured = self.config.get("tools", {})
        return {name for name in TOOLS if bool(configured.get(name, False))}

    def refresh_tools(self):
        self.router = CommandRouter(self.config, self.ollama_manager, self.alias_manager) if self.ollama_manager else self.router

    def send(self, text):
        if self._thread and self._thread.isRunning():
            return
        text = text.strip()
        if not text:
            return

        self.conversation.add("user", text)

        if self.router:
            try:
                direct = self.router.route(
                    text,
                    self._confirm_direct,
                    self._confirm_alias,
                )
            except Exception as exc:
                direct = f"Не удалось выполнить прямую команду: {exc}"
            if direct is not None:
                self.conversation.add("assistant", direct)
                self.direct_response.emit(direct)
                return

        self._current_answer = ""
        enabled_tools = self._enabled_tools()
        request = ChatRequest(
            model=self.config.get("model"),
            messages=self.conversation.as_ollama_messages(),
            thinking=self.config.get("thinking"),
            temperature=float(self.config.get("temperature")),
            context_length=int(self.config.get("context_length")),
            max_tokens=int(self.config.get("max_tokens")),
            tools=ollama_tools(enabled_tools),
        )

        self._thread = QThread()
        self._worker = GenerationWorker(self.provider, request, self.config, self.alias_manager)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.confirmation_requested.connect(self._on_confirmation_requested)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._cleanup)
        self._thread.start()

    def _on_chunk(self, chunk):
        if chunk.text:
            self._current_answer += chunk.text
        self.chunk_received.emit(chunk)

    def _on_finished(self, stats):
        if self._current_answer.strip():
            self.conversation.add("assistant", self._current_answer)
        self.generation_finished.emit(stats)

    def _on_failed(self, error):
        self.error.emit(error)

    def _confirm_direct(self, tool_name, arguments):
        return self._show_confirmation(tool_name, arguments)

    @staticmethod
    def _confirm_alias(query, target, category):
        label = {
            "applications": "приложению",
            "files": "файлу",
            "folders": "папке",
            "actions": "действию",
        }.get(category, "объекту")
        answer = QMessageBox.question(
            None,
            "Сохранить алиас",
            f"Я нашёл «{target}». Сохранить «{query}» как дополнительное название этому {label}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _on_confirmation_requested(self, tool_name, arguments, payload):
        event, result = payload
        result[0] = self._show_confirmation(tool_name, arguments)
        event.set()

    @staticmethod
    def _show_confirmation(tool_name, arguments):
        labels = {
            "delete_file": "Подтверждение удаления",
            "write_file": "Подтверждение перезаписи",
            "rename_file": "Подтверждение переименования",
            "copy_file": "Подтверждение копирования",
            "move_file": "Подтверждение перемещения",
            "close_application": "Подтверждение закрытия приложения",
        }
        title = labels.get(tool_name, "Подтверждение действия")
        description = json.dumps(arguments, ensure_ascii=False, indent=2)
        answer = QMessageBox.question(
            None,
            title,
            description,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _cleanup(self):
        if self._worker:
            self._worker.deleteLater()
        if self._thread:
            self._thread.deleteLater()
        self._worker = None
        self._thread = None

    def add_assistant_message(self, text):
        if text and text.strip():
            self.conversation.add("assistant", text)
