from __future__ import annotations

import re

from tools.executor import ToolExecutor
from tools.registry import TOOLS


class CommandRouter:
    """Определяет однозначные русскоязычные команды, которым не нужен LLM."""

    def __init__(self, config, ollama_manager):
        self.config = config
        self.ollama_manager = ollama_manager

    def _executor(self) -> ToolExecutor:
        return ToolExecutor(self.config, set(TOOLS))

    @staticmethod
    def _reply(result: dict) -> str:
        if not result.get("success"):
            return f"Не выполнено: {result.get('error', 'неизвестная ошибка')}"
        details = result.get("details") or {}
        if result.get("matches") is not None:
            matches = result.get("matches") or []
            if not matches:
                return "Ничего не найдено."
            return "Найдено:\n" + "\n".join(matches[:20])
        if result.get("running") is not None:
            return "Приложение запущено." if result["running"] else "Приложение не запущено."
        if result.get("path"):
            return f"Готово: {result['path']}"
        if details:
            return "Готово."
        return "Готово."

    def route(self, text: str, confirmation_callback=None) -> str | None:
        normalized = " ".join(text.strip().split())
        lower = normalized.lower()
        executor = self._executor()

        if re.fullmatch(r"(?:статус|состояние) ollama", lower):
            return f"Ollama Server: {self.ollama_manager.server_status()}. Загружено моделей: {len(self.ollama_manager.get_loaded_models())}."

        if lower in {"запусти ollama", "запустить ollama", "запусти сервер ollama", "запустить сервер ollama"}:
            try:
                self.ollama_manager.start()
                return "Ollama Server запущен."
            except Exception as exc:
                return f"Не удалось запустить Ollama: {exc}"

        if lower in {"останови ollama", "остановить ollama", "останови сервер ollama", "остановить сервер ollama"}:
            result = self.ollama_manager.stop_server()
            return "Ollama Server остановлен." if result.get("success") else f"Не удалось остановить Ollama: {result.get('error')}"

        match = re.fullmatch(r"(?:найди|поищи|покажи) (?:файл |файлы )?(.+)", normalized, flags=re.I)
        if match and executor._is_enabled("search_files"):
            result = executor.execute("search_files", {"name": match.group(1)}, confirmation_callback=confirmation_callback)
            return self._reply(result)

        match = re.fullmatch(r"(?:удали|удалить|стереть|сотри) (?:файл |файлы )?(.+)", normalized, flags=re.I)
        if match and executor._is_enabled("delete_file"):
            result = executor.execute("delete_file", {"path": match.group(1)}, confirmation_callback=confirmation_callback)
            return self._reply(result)

        match = re.fullmatch(r"(?:проверь|проверить),? (.+)", normalized, flags=re.I)
        if match and executor._is_enabled("get_process_status"):
            result = executor.execute("get_process_status", {"name": match.group(1)}, confirmation_callback=confirmation_callback)
            return self._reply(result)

        match = re.fullmatch(r"(?:открой|открыть|запусти|запустить) (.+)", normalized, flags=re.I)
        if match and executor._is_enabled("launch_application"):
            target = match.group(1)
            status = executor.execute("get_process_status", {"name": target}, confirmation_callback=confirmation_callback) if executor._is_enabled("get_process_status") else {"running": False}
            if status.get("success") and status.get("running"):
                return f"{target} уже запущен."
            result = executor.execute("launch_application", {"target": target}, confirmation_callback=confirmation_callback)
            return self._reply(result)

        return None
