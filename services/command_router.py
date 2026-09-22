from __future__ import annotations

import logging
import re
import time

from core.alias_manager import AliasManager, DEFAULT_ACTION_ALIASES
from tools import applications
from tools.executor import ToolExecutor
from tools.paths import get_workspace_index
from core.target_resolver import TargetResolver
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
        self.target_resolver = TargetResolver(self.alias_manager, get_workspace_index)
        self.ui_controller = None
        logger.debug("router_created")

    def set_ui_controller(self, controller) -> None:
        """Подключает UI для команд, которые относятся к самому Jarvis и его окну."""
        self.ui_controller = controller
        logger.debug("router_ui_controller_set controller=%s", type(controller).__name__)

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
        """Разрешает цель даже если она является частью естественной фразы."""
        return self.target_resolver.resolve(
            query,
            categories,
            alias_confirmation_callback=alias_confirmation_callback,
            use_workspace_index=use_workspace_index,
        )

    def _direct_tool(self, tool_name: str, arguments: dict, confirmation_callback=None) -> str:
        result = self._executor().execute(
            tool_name,
            arguments,
            confirmation_callback=confirmation_callback,
        )
        return self._reply(result)

    def _route_extended_tools(self, text: str, confirmation_callback=None, alias_confirmation_callback=None) -> str | None:
        """Прямые маршруты для всех инструментов, которые иначе доступны LLM."""
        lower = " ".join(text.lower().split())
        executor = self._executor()

        # Создание файла/папки.
        match = re.fullmatch(r"(?:создай|создать)\s+(?:новый\s+)?файл\s+(.+?)(?:\s+с\s+(?:содержимым|текстом))?\s*", text, re.IGNORECASE)
        if match and executor._is_enabled("create_file"):
            path = match.group(1).strip().strip("\"'")
            return self._direct_tool("create_file", {"path": path, "content": ""}, confirmation_callback)

        match = re.fullmatch(r"(?:создай|создать)\s+(?:новую\s+)?папку\s+(.+?)\s*", text, re.IGNORECASE)
        if match and executor._is_enabled("create_folder"):
            path = match.group(1).strip().strip("\"'")
            return self._direct_tool("create_folder", {"path": path}, confirmation_callback)

        # Запись файла. Форматы: «запиши в файл X: текст» / «перезапиши файл X на текст».
        match = re.fullmatch(
            r"(?:запиши|записать|перезапиши|перезаписать)\s+(?:в\s+)?(?:файл\s+)?(.+?)\s+(?:на|содержимым|текстом|со\s+текстом)\s+(.+)",
            text,
            re.IGNORECASE,
        )
        if match and executor._is_enabled("write_file"):
            path, content = match.groups()
            return self._direct_tool("write_file", {"path": path.strip().strip("\"'"), "content": content.strip()}, confirmation_callback)

        # Двоеточие удобно для диктовки: «запиши в файл test.txt: привет».
        match = re.fullmatch(r"(?:запиши|перезапиши)\s+(?:в\s+)?(?:файл\s+)?(.+?)\s*:\s*(.+)", text, re.IGNORECASE)
        if match and executor._is_enabled("write_file"):
            path, content = match.groups()
            return self._direct_tool("write_file", {"path": path.strip().strip("\"'"), "content": content.strip()}, confirmation_callback)

        # Переименование/копирование/перемещение.
        match = re.fullmatch(r"(?:переименуй|переименовать)\s+(?:файл\s+)?(.+?)\s+(?:в|на)\s+(.+)", text, re.IGNORECASE)
        if match and executor._is_enabled("rename_file"):
            path, new_name = match.groups()
            return self._direct_tool("rename_file", {"path": path.strip().strip("\"'"), "new_name": new_name.strip().strip("\"'")}, confirmation_callback)

        match = re.fullmatch(r"(?:скопируй|скопировать)\s+(?:файл\s+)?(.+?)\s+(?:в|в папку|на)\s+(.+)", text, re.IGNORECASE)
        if match and executor._is_enabled("copy_file"):
            path, destination = match.groups()
            return self._direct_tool("copy_file", {"path": path.strip().strip("\"'"), "destination": destination.strip().strip("\"'")}, confirmation_callback)

        match = re.fullmatch(r"(?:перемести|переместить)\s+(?:файл\s+)?(.+?)\s+(?:в|в папку|на)\s+(.+)", text, re.IGNORECASE)
        if match and executor._is_enabled("move_file"):
            path, destination = match.groups()
            return self._direct_tool("move_file", {"path": path.strip().strip("\"'"), "destination": destination.strip().strip("\"'")}, confirmation_callback)

        # Информация о файле.
        match = re.fullmatch(r"(?:информация|сведения|свойства)\s+(?:о\s+)?(?:файле\s+)?(.+)", text, re.IGNORECASE)
        if match and executor._is_enabled("file_info"):
            path = match.group(1).strip().strip("\"'")
            return self._direct_tool("file_info", {"path": path}, confirmation_callback)

        # Поиск приложения.
        match = re.fullmatch(r"(?:найди|найти)\s+(?:приложение|приложения|программу|программа)\s+(.+)", text, re.IGNORECASE)
        if match and executor._is_enabled("find_application"):
            name = match.group(1).strip()
            return self._direct_tool("find_application", {"name": name}, confirmation_callback)

        # Открытие URL.
        match = re.fullmatch(r"(?:открой|открыть)\s+(https?://\S+)", text, re.IGNORECASE)
        if match and executor._is_enabled("open_url"):
            return self._direct_tool("open_url", {"url": match.group(1)}, confirmation_callback)

        # Управление окнами обычных приложений. Алиасы приложения разрешаются
        # тем же TargetResolver, что и для запуска/закрытия.
        action = self._resolve_action(lower)
        if action and action[0] == "minimize" and executor._is_enabled("minimize_application"):
            target = action[1]
            if target.strip().casefold() in self._GENERIC_APPLICATION_TARGETS:
                return "Какое приложение свернуть?"
            resolved, error = self._resolve_target(target, ("applications",), alias_confirmation_callback)
            if error:
                return f"Не выполнено: {error}"
            result = executor.execute("minimize_application", {"name": resolved}, confirmation_callback=confirmation_callback)
            if result.get("success"):
                return f"{target} свернут."
            return f"Не удалось свернуть {target}: {result.get('error', 'неизвестная ошибка')}"

        # Специальные команды Jarvis/окна. Они намеренно НЕ являются LLM tools.
        if self.ui_controller is not None:
            assistant_name = str(self.config.get("assistant_name", "JARVIS")).strip().casefold()
            shutdown_commands = {
                "закрой себя",
                "закрой джарвис",
                "закрой jarvis",
                "выключись",
                "закройся",
                "заверши работу",
            }
            if assistant_name:
                shutdown_commands.add(f"закрой {assistant_name}")

            if lower in shutdown_commands:
                shutdown = getattr(self.ui_controller, "shutdown", None)
                if callable(shutdown):
                    shutdown()
                else:
                    # Запасной вариант для старых UI-контроллеров.
                    self.ui_controller.close()
                return "Полностью закрываю Jarvis."

            if lower in {"свернись", "сверни окно", "свернись в трей", "сверни jarvis"}:
                minimize = getattr(self.ui_controller, "minimize_window", None)
                if callable(minimize):
                    minimize()
                else:
                    self.ui_controller.showMinimized()
                return "Сворачиваю окно."

            if lower in {"развернись", "разверни окно", "разверни jarvis", "на весь экран", "сделай окно на весь экран"}:
                maximize = getattr(self.ui_controller, "maximize_window", None)
                if callable(maximize):
                    maximize()
                else:
                    self.ui_controller.showMaximized()
                return "Разворачиваю окно."

            if lower in {"восстанови окно", "верни обычный размер", "сделай окно обычным", "верни окно"}:
                restore = getattr(self.ui_controller, "restore_window", None)
                if callable(restore):
                    restore()
                else:
                    self.ui_controller.showNormal()
                return "Восстанавливаю обычный размер окна."

        # Ollama и модель. Русские варианты намеренно широкие: Vosk часто
        # искажает «Ollama» и название Qwen.
        model = str(self.config.get("model", "")).strip()
        model_aliases = {
            "модель", "модел", "квен", "квэн", "квен 3", "квэн 3", "квен3", "квэн3",
            "qwen", "qwen 3", "qwen3", "qwen3 1.7b", "qwen 1.7b",
            "ллм", "ллмку", "ллам", "llm",
        }
        model_action = re.fullmatch(
            r"(?:выгрузи|выгрузить|освободи|освободить|закрой|закрыть|останови|остановить|выключи|выключить)"
            r"\s+(?:текущую\s+)?(.+)",
            lower,
        )
        if model_action:
            target = model_action.group(1).strip()
            if target in model_aliases or any(alias in target for alias in model_aliases if alias not in {"модель"}):
                result = self.ollama_manager.unload_model(model)
                return f"Модель {model} выгружена." if result.get("success") else f"Не удалось выгрузить модель: {result.get('error', 'неизвестная ошибка')}"

        ollama_aliases = {
            "оллама", "олламу", "олламы", "оллам", "оллама", "ollama",
            "сервер оллама", "сервер ollama", "сервер ламы", "сервер лам",
        }
        server_action = re.fullmatch(
            r"(?:закрой|закрыть|останови|остановить|выключи|выключить|заверши|завершить)"
            r"\s+(.+)",
            lower,
        )
        if server_action and server_action.group(1).strip() in ollama_aliases:
            result = self.ollama_manager.stop_server()
            return "Ollama Server остановлен." if result.get("success") else f"Не удалось остановить Ollama: {result.get('error', 'неизвестная ошибка')}"

        if lower in {"выгрузи модель", "выгрузить модель", "выгрузи текущую модель", "освободи модель", "освободи память от модели"}:
            result = self.ollama_manager.unload_model(model)
            return f"Модель {model} выгружена." if result.get("success") else f"Не удалось выгрузить модель: {result.get('error', 'неизвестная ошибка')}"

        return None

    def command_catalog(self) -> list[dict[str, object]]:
        """Возвращает справочник команд, которые обрабатывает сам Command Router."""
        catalog = [
            {
                "name": "Открыть приложение",
                "commands": list(DEFAULT_ACTION_ALIASES["launch"]),
            },
            {
                "name": "Закрыть приложение",
                "commands": list(DEFAULT_ACTION_ALIASES["close"]),
            },
            {
                "name": "Найти файл или папку",
                "commands": list(DEFAULT_ACTION_ALIASES["search"]),
            },
            {
                "name": "Прочитать файл",
                "commands": list(DEFAULT_ACTION_ALIASES["read"]),
            },
            {
                "name": "Удалить файл",
                "commands": list(DEFAULT_ACTION_ALIASES["delete"]),
            },
            {
                "name": "Проверить приложение",
                "commands": list(DEFAULT_ACTION_ALIASES["status"]),
            },
            {
                "name": "Свернуть приложение",
                "commands": list(DEFAULT_ACTION_ALIASES["minimize"]),
            },
            {
                "name": "Создать файл",
                "commands": ["создай файл <имя>", "создать файл <имя>"],
            },
            {
                "name": "Создать папку",
                "commands": ["создай папку <имя>", "создать папку <имя>"],
            },
            {
                "name": "Записать / перезаписать файл",
                "commands": [
                    "запиши в файл <имя> на <текст>",
                    "запиши в файл <имя>: <текст>",
                    "перезапиши файл <имя> на <текст>",
                    "перезапиши файл <имя>: <текст>",
                ],
            },
            {
                "name": "Переименовать файл",
                "commands": ["переименуй файл <имя> в <новое имя>", "переименовать файл <имя> в <новое имя>"],
            },
            {
                "name": "Скопировать файл",
                "commands": ["скопируй файл <имя> в <папку>", "скопировать файл <имя> в <папку>"],
            },
            {
                "name": "Переместить файл",
                "commands": ["перемести файл <имя> в <папку>", "переместить файл <имя> в <папку>"],
            },
            {
                "name": "Информация о файле",
                "commands": ["информация о файле <имя>", "сведения о файле <имя>", "свойства файла <имя>"],
            },
            {
                "name": "Найти приложение",
                "commands": ["найди приложение <имя>", "найти приложение <имя>"],
            },
            {
                "name": "Открыть URL",
                "commands": ["открой <http://...>", "открыть <https://...>"],
            },
            {
                "name": "Статус Ollama",
                "commands": ["статус ollama", "состояние ollama"],
            },
            {
                "name": "Запустить Ollama",
                "commands": ["запусти ollama", "запустить ollama", "запусти сервер ollama", "запустить сервер ollama"],
            },
            {
                "name": "Остановить Ollama",
                "commands": ["останови ollama", "остановить ollama", "останови сервер ollama", "остановить сервер ollama"],
            },
            {
                "name": "Выгрузить модель",
                "commands": ["выгрузи модель", "выгрузить модель", "выгрузи текущую модель", "освободи модель", "освободи память от модели"],
            },
            {
                "name": "Свернуть окно Jarvis",
                "commands": ["свернись", "сверни окно", "свернись в трей", "сверни jarvis"],
            },
            {
                "name": "Развернуть окно Jarvis",
                "commands": ["развернись", "разверни окно", "разверни jarvis", "на весь экран", "сделай окно на весь экран"],
            },
            {
                "name": "Восстановить обычный размер окна Jarvis",
                "commands": ["восстанови окно", "верни обычный размер", "сделай окно обычным", "верни окно"],
            },
            {
                "name": "Закрыть Jarvis",
                "commands": ["закрой себя", "закрой джарвис", "закрой jarvis", "выключись", "закройся", "заверши работу"],
            },
        ]

        # Пользовательские алиасы действий тоже относятся к фактически
        # распознаваемым Router-командам, поэтому показываем их рядом с
        # встроенными вариантами.
        custom_actions = self.alias_manager.data.get("actions", {})
        by_name = {item["name"]: item for item in catalog}
        action_names = {
            "launch": "Открыть приложение",
            "close": "Закрыть приложение",
            "search": "Найти файл или папку",
            "read": "Прочитать файл",
            "delete": "Удалить файл",
            "status": "Проверить приложение",
            "minimize": "Свернуть приложение",
        }
        for action, entry in custom_actions.items():
            name = action_names.get(action)
            if not name:
                continue
            item = by_name.get(name)
            if item:
                existing = {str(command).casefold() for command in item["commands"]}
                for alias in entry.get("aliases", []):
                    if str(alias).casefold() not in existing:
                        item["commands"].append(alias)

        return catalog

    def tools_for_message(self, text: str) -> set[str]:
        """Определяет набор LLM-инструментов для текущего сообщения."""
        lower = " ".join(text.lower().split())
        action = self._resolve_action(lower)
        executor = self._executor()
        enabled = {name for name in TOOLS if executor._is_enabled(name)}

        action_tools = {
            "launch": {"launch_application", "get_process_status"},
            "close": {"close_application", "get_process_status"},
            "minimize": {"minimize_application", "get_process_status"},
            "status": {"get_process_status"},
            "search": {"search_files"},
            "read": {"read_file"},
            "delete": {"delete_file", "search_files"},
        }

        detected_actions: set[str] = set()
        for action_name, aliases in DEFAULT_ACTION_ALIASES.items():
            if any(self._contains_action_alias(lower, action_name, alias) for alias in aliases):
                detected_actions.add(action_name)

        if len(detected_actions) > 1:
            selected = set()
            for action_name in detected_actions:
                selected.update(action_tools.get(action_name, set()))
            result = selected & enabled
            logger.info("router_tool_scope text=%r tools=%s reason=compound_actions actions=%s", text, sorted(result), sorted(detected_actions))
            return result

        if action:
            selected = action_tools.get(action[0])
            if selected:
                result = selected & enabled
                logger.info("router_tool_scope text=%r tools=%s reason=action", text, sorted(result))
                return result

        keyword_tools = {
            "файл": {"search_files", "read_file", "file_info", "create_file", "write_file", "delete_file", "rename_file", "copy_file", "move_file"},
            "файла": {"search_files", "read_file", "file_info", "create_file", "write_file", "delete_file", "rename_file", "copy_file", "move_file"},
            "папк": {"search_files", "create_folder", "file_info", "copy_file", "move_file"},
            "приложен": {"find_application", "get_process_status", "launch_application", "close_application"},
            "програм": {"find_application", "get_process_status", "launch_application", "close_application"},
            "сайт": {"open_url"},
            "ссылк": {"open_url"},
            "url": {"open_url"},
        }
        selected = set()
        for keyword, names in keyword_tools.items():
            if keyword in lower:
                selected.update(names)

        result = selected & enabled
        logger.info("router_tool_scope text=%r tools=%s reason=keywords_or_chat", text, sorted(result))
        return result

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

        extended = self._route_extended_tools(normalized, confirmation_callback, alias_confirmation_callback)
        if extended is not None:
            return extended

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
