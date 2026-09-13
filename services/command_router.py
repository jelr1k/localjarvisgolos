from __future__ import annotations

import re

from core.alias_manager import AliasManager
from tools import applications
from tools.executor import ToolExecutor
from tools.registry import TOOLS


class CommandRouter:
    """Определяет однозначные русскоязычные команды, которым не нужен LLM."""

    def __init__(self, config, ollama_manager, alias_manager: AliasManager | None = None):
        self.config = config
        self.ollama_manager = ollama_manager
        self.alias_manager = alias_manager or AliasManager()

    def _executor(self) -> ToolExecutor:
        return ToolExecutor(self.config, set(TOOLS), self.alias_manager)

    @staticmethod
    def _reply(result: dict) -> str:
        if not result.get("success"):
            matches = result.get("matches") or []
            if result.get("ambiguous") and matches:
                return (result.get("error") or "Неоднозначный запрос.")
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

    def _resolve_target(self, query, categories, alias_confirmation_callback=None):
        exact = self.alias_manager.resolve_any(query, categories)
        if exact.get("status") == "exact":
            return exact["target"], None
        if exact.get("status") == "ambiguous":
            return None, "Неоднозначный алиас: " + ", ".join(exact.get("candidates", []))

        suggestions = self.alias_manager.suggest_any(query, categories, limit=5)
        if not suggestions:
            return query, None
        if len(suggestions) > 1 and suggestions[0]["score"] - suggestions[1]["score"] < 0.08:
            items = [item["target"] for item in suggestions[:5]]
            return None, "Не удалось однозначно определить объект. Варианты: " + "; ".join(items)

        suggestion = suggestions[0]
        if alias_confirmation_callback is None:
            return query, None
        accepted = alias_confirmation_callback(query, suggestion["target"], suggestion["category"])
        if not accepted:
            return query, None
        self.alias_manager.add_alias(suggestion["category"], suggestion["target"], query)
        return suggestion["target"], None

    def route(self, text: str, confirmation_callback=None, alias_confirmation_callback=None) -> str | None:
        normalized = " ".join(text.strip().split())
        lower = normalized.lower()
        executor = self._executor()

        if applications.has_pending_launch_choices() and re.fullmatch(r"(?:\d+|перв(?:ый|ая)|втор(?:ой|ая)|трет(?:ий|ья)|четверт(?:ый|ая)|четвёрт(?:ый|ая)|пят(?:ый|ая))\.?", lower):
            return self._reply(executor.execute("launch_application", {"target": normalized}, confirmation_callback=confirmation_callback))

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

        action = self.alias_manager.resolve_action(normalized)
        if not action:
            return None
        action_name, target = action

        if action_name == "search" and executor._is_enabled("search_files"):
            target = re.sub(r"^(?:файл|файлы)\s+", "", target, flags=re.IGNORECASE)
            resolved, error = self._resolve_target(target, ("files", "folders"), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            return self._reply(executor.execute("search_files", {"name": resolved}, confirmation_callback=confirmation_callback))

        if action_name == "delete" and executor._is_enabled("delete_file"):
            target = re.sub(r"^(?:файл|файлы)\s+", "", target, flags=re.IGNORECASE)
            resolved, error = self._resolve_target(target, ("files",), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            return self._reply(executor.execute("delete_file", {"path": resolved}, confirmation_callback=confirmation_callback))

        if action_name == "status" and executor._is_enabled("get_process_status"):
            resolved, error = self._resolve_target(target, ("applications",), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            return self._reply(executor.execute("get_process_status", {"name": resolved}, confirmation_callback=confirmation_callback))

        if action_name == "launch" and executor._is_enabled("launch_application"):
            resolved, error = self._resolve_target(target, ("applications", "files", "folders"), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            status = executor.execute("get_process_status", {"name": resolved}, confirmation_callback=confirmation_callback) if executor._is_enabled("get_process_status") else {"running": False}
            if status.get("success") and status.get("running"):
                return f"{target} уже запущен."
            return self._reply(executor.execute("launch_application", {"target": resolved}, confirmation_callback=confirmation_callback))

        if action_name == "close" and executor._is_enabled("close_application"):
            resolved, error = self._resolve_target(target, ("applications",), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            return self._reply(executor.execute("close_application", {"name": resolved}, confirmation_callback=confirmation_callback))

        return None
