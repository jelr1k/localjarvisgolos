from __future__ import annotations

import logging
import re
import time

from core.alias_manager import AliasManager, DEFAULT_ACTION_ALIASES
from tools import applications
from tools.executor import ToolExecutor
from tools.paths import get_workspace_index
from tools.registry import TOOLS

logger = logging.getLogger("jarvis.router")


class CommandRouter:
    """Определяет однозначные команды, которым не нужен LLM."""

    _GENERIC_APPLICATION_TARGETS = {"приложение", "приложения", "программу", "программа"}
    _CONTEXTUAL_SEARCH_ALIASES = {"где находится", "где лежит", "расположение", "местоположение", "покажи"}
    _FILE_SEARCH_CONTEXT_RE = re.compile(
        r"(?:\bфайл(?:а|ы|ом|ов)?\b|\bпапк\w*\b|\bкаталог\w*\b|\bдиректор\w*\b|\bдокумент\w*\b|[\\/]"
        r"|\b[\wА-Яа-яЁё-]+\.[A-Za-z0-9]{1,8}\b)",
        flags=re.IGNORECASE,
    )

    def __init__(self, config, ollama_manager, alias_manager: AliasManager | None = None):
        self.config = config
        self.ollama_manager = ollama_manager
        self.alias_manager = alias_manager or AliasManager()
        logger.debug("router_created")

    def _executor(self) -> ToolExecutor:
        return ToolExecutor(self.config, set(TOOLS), self.alias_manager)

    @classmethod
    def _is_contextual_file_search(cls, alias: str, target: str) -> bool:
        if alias not in cls._CONTEXTUAL_SEARCH_ALIASES:
            return True
        return bool(cls._FILE_SEARCH_CONTEXT_RE.search(target))

    @classmethod
    def _contains_action_alias(cls, text: str, action: str, alias: str) -> bool:
        pattern = rf"(?<!\w){re.escape(alias)}(?!\w)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return False
        if action != "search" or alias not in cls._CONTEXTUAL_SEARCH_ALIASES:
            return True
        target = text[match.end():].lstrip(" ,:;—-\t")
        return cls._is_contextual_file_search(alias, target)

    def _has_multiple_actions(self, text: str) -> bool:
        normalized = " ".join(text.strip().split())
        if not normalized:
            return False
        matches = []
        for action, defaults in DEFAULT_ACTION_ALIASES.items():
            for alias in defaults:
                if self._contains_action_alias(normalized, action, alias):
                    matches.append(action)
                    break
        for action, entry in self.alias_manager.data.get("actions", {}).items():
            for alias in entry.get("aliases", []):
                if self._contains_action_alias(normalized, action, alias):
                    matches.append(action)
                    break
        unique_actions = set(matches)
        if len(unique_actions) > 1:
            logger.info("compound_command detected actions=%s text=%r", sorted(unique_actions), text)
            return True
        return False

    def _resolve_action(self, text: str):
        action = self.alias_manager.resolve_action(text)
        if not action:
            return None
        action_name, target = action
        if action_name == "search":
            for alias in self._CONTEXTUAL_SEARCH_ALIASES:
                if re.match(rf"^{re.escape(alias)}(?:,)?\s+", text, flags=re.IGNORECASE):
                    if not self._is_contextual_file_search(alias, target):
                        logger.info("contextual_search_rejected target=%r text=%r", target, text)
                        return None
                    break
        return action

    @staticmethod
    def _reply(result: dict, include_path: bool = True) -> str:
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

    def _resolve_target(self, query, categories, alias_confirmation_callback=None, *, use_workspace_index=False):
        """Разрешает цель через реальный Workspace index либо AliasManager."""
        logger.debug("resolve_target query=%r categories=%r workspace_index=%s", query, categories, use_workspace_index)

        if use_workspace_index:
            entry, matches = get_workspace_index().resolve(query, categories, self.alias_manager, fuzzy=True)
            if entry is not None:
                logger.debug("workspace_index_exact query=%r target=%s", query, entry.path)
                return str(entry.path), None
            if len(matches) > 1:
                candidates = [str(item.path) for item in matches]
                return None, "Не удалось однозначно определить объект. Варианты: " + "; ".join(candidates[:5])

        exact = self.alias_manager.resolve_any(query, categories)
        logger.debug("resolve_target alias=%r", exact)
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
        started = time.perf_counter()
        normalized = " ".join(text.strip().split())
        lower = normalized.lower()
        logger.info("route_start text=%r normalized=%r", text, normalized)
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
                logger.exception("route_ollama_start_failed")
                return f"Не удалось запустить Ollama: {exc}"

        if lower in {"останови ollama", "остановить ollama", "останови сервер ollama", "остановить сервер ollama"}:
            result = self.ollama_manager.stop_server()
            return "Ollama Server остановлен." if result.get("success") else f"Не удалось остановить Ollama: {result.get('error')}"

        if self._has_multiple_actions(normalized):
            return None

        action = self._resolve_action(normalized)
        if not action:
            return None
        action_name, target = action

        if action_name == "search" and executor._is_enabled("search_files"):
            target = re.sub(r"^(?:файл|файлы)\s+", "", target, flags=re.IGNORECASE)
            return self._reply(executor.execute("search_files", {"name": target}, confirmation_callback=confirmation_callback))

        if action_name == "read" and executor._is_enabled("read_file"):
            target = re.sub(r"^(?:файл|файлы)\s+", "", target, flags=re.IGNORECASE)
            result = executor.execute("read_file", {"path": target}, confirmation_callback=confirmation_callback)
            return self._reply(result, include_path=False)

        if action_name == "delete" and executor._is_enabled("delete_file"):
            target = re.sub(r"^(?:файл|файлы)\s+", "", target, flags=re.IGNORECASE)
            resolved, error = self._resolve_target(target, ("files",), alias_confirmation_callback, use_workspace_index=True)
            if error:
                return f"Не выполнено: {error}"
            return self._reply(executor.execute("delete_file", {"path": resolved}, confirmation_callback=confirmation_callback))

        if action_name == "status" and executor._is_enabled("get_process_status"):
            resolved, error = self._resolve_target(target, ("applications",), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            return self._reply(executor.execute("get_process_status", {"name": resolved}, confirmation_callback=confirmation_callback))

        if action_name == "launch" and executor._is_enabled("launch_application"):
            resolved, error = self._resolve_target(
                target,
                ("applications", "files", "folders"),
                alias_confirmation_callback,
                use_workspace_index=True,
            )
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

        return None
