from __future__ import annotations

from tools.registry import TOOLS
from security.permissions import PermissionManager


class ToolExecutor:
    """Единая точка запуска инструментов с проверкой разрешений."""

    def __init__(self, config=None, enabled_tools=None):
        self.permission_manager = PermissionManager(config) if config is not None else None
        self.enabled_tools = set(enabled_tools) if enabled_tools is not None else set(TOOLS)

    def _is_enabled(self, tool_name: str) -> bool:
        if tool_name not in self.enabled_tools:
            return False
        if self.permission_manager is not None:
            return self.permission_manager.is_enabled(tool_name)
        return True

    def execute(self, tool_name: str, arguments: dict | None = None, confirmation_callback=None) -> dict:
        if tool_name not in TOOLS:
            return {"success": False, "error": f"Неизвестный инструмент: {tool_name}"}
        if not self._is_enabled(tool_name):
            return {"success": False, "error": "Инструмент отключён в настройках Jarvis."}
        if not isinstance(arguments, dict):
            return {"success": False, "error": "Параметры инструмента должны быть объектом."}

        tool = TOOLS[tool_name]
        if tool.get("requires_confirmation", False):
            if confirmation_callback is None:
                return {"success": False, "error": "Для этого действия требуется подтверждение пользователя."}
            if not confirmation_callback(tool_name, arguments):
                return {"success": False, "error": "Пользователь отменил действие."}

        try:
            result = tool["function"](**arguments)
            if not isinstance(result, dict) or "success" not in result:
                return {"success": False, "error": "Инструмент вернул некорректный результат."}
            return result
        except TypeError as exc:
            return {"success": False, "error": f"Неверные аргументы инструмента: {exc}"}
        except Exception as exc:
            return {"success": False, "error": f"Ошибка инструмента: {exc}"}

    def requires_confirmation(self, tool_name: str) -> bool:
        tool = TOOLS.get(tool_name)
        return bool(tool and tool.get("requires_confirmation", False))
