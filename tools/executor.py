from __future__ import annotations

import logging

from security.permissions import PermissionManager
from tools.registry import TOOLS


logger = logging.getLogger("jarvis.tools")


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
        logger.info("tool=%s invoked", tool_name)
        if tool_name not in TOOLS:
            logger.warning("tool=%s unknown", tool_name)
            return {"success": False, "error": f"Неизвестный инструмент: {tool_name}"}
        if not self._is_enabled(tool_name):
            logger.warning("tool=%s disabled", tool_name)
            return {"success": False, "error": "Инструмент отключён в настройках Jarvis."}
        if not isinstance(arguments, dict):
            return {"success": False, "error": "Параметры инструмента должны быть объектом."}

        tool = TOOLS[tool_name]
        if tool.get("requires_confirmation", False):
            if confirmation_callback is None:
                return {"success": False, "error": "Для этого действия требуется подтверждение пользователя."}
            if not confirmation_callback(tool_name, arguments):
                logger.info("tool=%s cancelled", tool_name)
                return {"success": False, "error": "Пользователь отменил действие."}

        try:
            result = tool["function"](**arguments)
            if not isinstance(result, dict) or "success" not in result:
                return {"success": False, "error": "Инструмент вернул некорректный результат."}
            logger.info("tool=%s success=%s", tool_name, result.get("success"))
            if not result.get("success"):
                logger.warning("tool=%s failed: %s", tool_name, result.get("error", "unknown"))
            return result
        except TypeError as exc:
            logger.exception("tool=%s invalid arguments", tool_name)
            return {"success": False, "error": f"Неверные аргументы инструмента: {exc}"}
        except Exception as exc:
            logger.exception("tool=%s crashed", tool_name)
            return {"success": False, "error": f"Ошибка инструмента: {exc}"}

    def requires_confirmation(self, tool_name: str) -> bool:
        tool = TOOLS.get(tool_name)
        return bool(tool and tool.get("requires_confirmation", False))
