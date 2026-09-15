from __future__ import annotations

import logging
import re
import time

from core.alias_manager import AliasManager
from tools import applications
from tools.executor import ToolExecutor
from tools.registry import TOOLS

logger = logging.getLogger("jarvis.router")


class CommandRouter:
    """Определяет однозначные русскоязычные команды, которым не нужен LLM."""

    _GENERIC_APPLICATION_TARGETS = {"приложение", "приложения", "программу", "программа"}

    def __init__(self, config, ollama_manager, alias_manager: AliasManager | None = None):
        self.config = config
        self.ollama_manager = ollama_manager
        self.alias_manager = alias_manager or AliasManager()
        logger.debug("router_created")

    def _executor(self) -> ToolExecutor:
        return ToolExecutor(self.config, set(TOOLS), self.alias_manager)

    def _has_multiple_actions(self, text: str) -> bool:
        """Составные команды должны попасть в LLM, чтобы он выстроил цепочку tools."""
        normalized = " ".join(text.strip().split())
        if not normalized:
            return False

        matches = []
        for action, defaults in self.alias_manager.DEFAULT_ACTION_ALIASES.items():
            for alias in defaults:
                pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
                if re.search(pattern, normalized, flags=re.IGNORECASE):
                    matches.append(action)
                    break

        # Пользовательские алиасы действий тоже учитываем.
        for action, entry in self.alias_manager.data.get("actions", {}).items():
            for alias in entry.get("aliases", []):
                pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
                if re.search(pattern, normalized, flags=re.IGNORECASE):
                    matches.append(action)
                    break

        unique_actions = set(matches)
        if len(unique_actions) > 1:
            logger.info("compound_command detected actions=%s text=%r", sorted(unique_actions), text)
            return True
        return False

    @staticmethod
    def _reply(result: dict, include_path: bool = True) -> str:
        logger.debug("router_reply result=%r include_path=%s", result, include_path)
        if not result.get("success"):
            matches = result.get("matches") or []
            if result.get("ambiguous") and matches:
                return result.get("error") or "Неоднозначный запрос."
            return f"Не выполнено: {result.get('error', 'неизвестная ошибка')}"
        if result.get("content") is not None:
            if include_path:
                path = result.get("path")
                prefix = f"Содержимое {path}:\n" if path else "Содержимое файла:\n"
            else:
                prefix = "Содержимое файла:\n"
            return prefix + str(result["content"])
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
        return "Готово."

    @staticmethod
    def _close_reply(target: str, result: dict) -> str:
        if not result.get("success"):
            matches = result.get("matches") or []
            if result.get("ambiguous") and matches:
                return result.get("error") or "Неоднозначный запрос."
            return f"Не удалось закрыть {target}: {result.get('error', 'неизвестная ошибка')}"
        if result.get("already_closed") or result.get("running") is False:
            return f"{target} уже закрыт."
        return f"{target} закрыт."

    def _resolve_target(self, query, categories, alias_confirmation_callback=None):
        logger.debug("resolve_target query=%r categories=%r", query, categories)
        exact = self.alias_manager.resolve_any(query, categories)
        logger.debug("resolve_target exact=%r", exact)
        if exact.get("status") == "exact":
            return exact["target"], None
        if exact.get("status") == "ambiguous":
            return None, "Неоднозначный алиас: " + ", ".join(exact.get("candidates", []))
        suggestions = self.alias_manager.suggest_any(query, categories, limit=5)
        logger.debug("resolve_target suggestions=%r", suggestions)
        if not suggestions:
            return query, None
        if len(suggestions) > 1 and suggestions[0]["score"] - suggestions[1]["score"] < 0.08:
            items = [item["target"] for item in suggestions[:5]]
            return None, "Не удалось однозначно определить объект. Варианты: " + "; ".join(items)
        suggestion = suggestions[0]
        if alias_confirmation_callback is None:
            return query, None
        accepted = alias_confirmation_callback(query, suggestion["target"], suggestion["category"])
        logger.info("alias_confirmation query=%r target=%r category=%s accepted=%s", query, suggestion["target"], suggestion["category"], accepted)
        if not accepted:
            return query, None
        self.alias_manager.add_alias(suggestion["category"], suggestion["target"], query)
        return suggestion["target"], None

    def route(self, text: str, confirmation_callback=None, alias_confirmation_callback=None) -> str | None:
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        lower = normalized.lower()
        logger.info("route_start text=%r normalized=%r", text, normalized)
        executor = self._executor()

        if applications.has_pending_launch_choices() and re.fullmatch(r"(?:\d+|перв(?:ый|ая)|втор(?:ой|ая)|трет(?:ий|ья)|четверт(?:ый|ая)|четвёрт(?:ый|ая)|пят(?:ый|ая))\.?", lower):
            result = self._reply(executor.execute("launch_application", {"target": normalized}, confirmation_callback=confirmation_callback))
            logger.info("route_finish branch=pending_launch_choice elapsed=%.4fs response=%r", time.perf_counter() - started, result)
            return result

        if re.fullmatch(r"(?:статус|состояние) ollama", lower):
            response = f"Ollama Server: {self.ollama_manager.server_status()}. Загружено моделей: {len(self.ollama_manager.get_loaded_models())}."
            logger.info("route_finish branch=ollama_status elapsed=%.4fs response=%r", time.perf_counter() - started, response)
            return response

        if lower in {"запусти ollama", "запустить ollama", "запусти сервер ollama", "запустить сервер ollama"}:
            try:
                self.ollama_manager.start()
                return "Ollama Server запущен."
            except Exception as exc:
                logger.exception("route_ollama_start_failed")
                return f"Не удалось запустить Ollama: {exc}"

        if lower in {"останови ollama", "остановить ollama", "останови сервер ollama", "остановить сервер ollama"}:
            result = self.ollama_manager.stop_server()
            return "Ollama Server остановлен." if result.get("success") else f"Не удалось остановить Ollama: {result.get('error')}"

        # Составные команды (например, «найди файл X, прочитай его и перескажи»)
        # не должны перехватываться первым совпавшим действием. Их должен
        # обработать LLM через последовательные tool_calls.
        if self._has_multiple_actions(normalized):
            logger.info("route_finish branch=compound_llm elapsed=%.4fs", time.perf_counter() - started)
            return None

        action = self.alias_manager.resolve_action(normalized)
        logger.debug("route_action_resolution result=%r", action)
        if not action:
            logger.info("route_finish branch=llm elapsed=%.4fs", time.perf_counter() - started)
            return None
        action_name, target = action
        logger.info("route_action action=%s target=%r", action_name, target)

        if action_name == "search" and executor._is_enabled("search_files"):
            target = re.sub(r"^(?:файл|файлы)\s+", "", target, flags=re.IGNORECASE)
            resolved, error = self._resolve_target(target, ("files", "folders"), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            return self._reply(executor.execute("search_files", {"name": resolved}, confirmation_callback=confirmation_callback))

        if action_name == "read" and executor._is_enabled("read_file"):
            target = re.sub(r"^(?:файл|файлы)\s+", "", target, flags=re.IGNORECASE)
            # read_file performs its own safe read-only path resolution. We do
            # not resolve through the alias resolver here because a searched
            # file may live in the read-only application root.
            result = executor.execute("read_file", {"path": target}, confirmation_callback=confirmation_callback)
            return self._reply(result, include_path=False)

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
            if target.strip().casefold() in self._GENERIC_APPLICATION_TARGETS:
                return "Какое приложение закрыть?"
            resolved, error = self._resolve_target(target, ("applications",), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            result = executor.execute("close_application", {"name": resolved}, confirmation_callback=confirmation_callback)
            return self._close_reply(resolved, result)

        logger.info("route_finish branch=unhandled_action action=%s elapsed=%.4fs response=%r", action_name, time.perf_counter() - started, None)
        return None
