from __future__ import annotations

import logging
import time

from core.alias_manager import AliasManager
from security.permissions import PermissionManager
from tools.registry import TOOLS


logger = logging.getLogger("jarvis.tools")


class ToolExecutor:
    """Единая точка запуска инструментов с проверкой разрешений."""

    def __init__(self, config=None, enabled_tools=None, alias_manager: AliasManager | None = None):
        self.permission_manager = PermissionManager(config) if config is not None else None
        self.enabled_tools = set(enabled_tools) if enabled_tools is not None else set(TOOLS)
        self.alias_manager = alias_manager or AliasManager()
        logger.debug("executor_created enabled_tools=%s", sorted(self.enabled_tools))

    def _is_enabled(self, tool_name: str) -> bool:
        enabled = tool_name in self.enabled_tools
        if self.permission_manager is not None:
            enabled = enabled and self.permission_manager.is_enabled(tool_name)
        logger.debug("tool_permission tool=%s enabled=%s", tool_name, enabled)
        return enabled

    def execute(self, tool_name: str, arguments: dict | None = None, confirmation_callback=None) -> dict:
        started = time.perf_counter()
        logger.info("tool_start name=%s arguments=%r", tool_name, arguments)
        if tool_name not in TOOLS:
            logger.warning("tool_unknown name=%s", tool_name)
            return {"success": False, "error": f"Неизвестный инструмент: {tool_name}"}
        if not self._is_enabled(tool_name):
            logger.warning("tool_disabled name=%s", tool_name)
            return {"success": False, "error": "Инструмент отключён в настройках Jarvis."}
        if not isinstance(arguments, dict):
            logger.error("tool_invalid_arguments name=%s type=%s", tool_name, type(arguments).__name__)
            return {"success": False, "error": "Параметры инструмента должны быть объектом."}

        try:
            resolved_arguments, alias_result = self.alias_manager.resolve_tool_arguments(tool_name, arguments)
            logger.debug("tool_alias_resolution name=%s before=%r after=%r result=%r", tool_name, arguments, resolved_arguments, alias_result)
            if alias_result:
                candidates = alias_result.get("candidates", [])
                if candidates:
                    logger.warning("tool_alias_ambiguous name=%s candidates=%r", tool_name, candidates)
                    return {
                        "success": False,
                        "error": "Неоднозначный алиас. Уточни объект.",
                        "ambiguous": True,
                        "matches": candidates,
                    }
            arguments = resolved_arguments

            if tool_name == "launch_application":
                arguments = dict(arguments)
                arguments["allow_outside_workspace"] = bool(
                    self.permission_manager.config.get("allow_outside_workspace", False)
                ) if self.permission_manager is not None else False
                logger.info(
                    "launch_workspace_policy allow_outside_workspace=%s target=%r",
                    arguments["allow_outside_workspace"],
                    arguments.get("target"),
                )

            tool = TOOLS[tool_name]
            if tool.get("requires_confirmation", False):
                logger.info("tool_confirmation_requested name=%s arguments=%r", tool_name, arguments)
                if confirmation_callback is None:
                    return {"success": False, "error": "Для этого действия требуется подтверждение пользователя."}
                accepted = confirmation_callback(tool_name, arguments)
                logger.info("tool_confirmation_result name=%s accepted=%s", tool_name, accepted)
                if accepted is None:
                    return {
                        "success": False,
                        "pending_confirmation": True,
                        "confirmation_tool": tool_name,
                        "confirmation_arguments": arguments,
                    }
                if not accepted:
                    return {"success": False, "error": "Пользователь отменил действие."}

            result = tool["function"](**arguments)
            if not isinstance(result, dict) or "success" not in result:
                logger.error("tool_invalid_result name=%s result=%r", tool_name, result)
                return {"success": False, "error": "Инструмент вернул некорректный результат."}
            elapsed = time.perf_counter() - started
            logger.info("tool_finish name=%s success=%s elapsed=%.4fs result=%r", tool_name, result.get("success"), elapsed, result)
            if not result.get("success"):
                logger.warning("tool_failed name=%s error=%s", tool_name, result.get("error", "unknown"))
            return result
        except TypeError as exc:
            logger.exception("tool_type_error name=%s", tool_name)
            return {"success": False, "error": f"Неверные аргументы инструмента: {exc}"}
        except Exception as exc:
            logger.exception("tool_crashed name=%s", tool_name)
            return {"success": False, "error": f"Ошибка инструмента: {exc}"}

    def requires_confirmation(self, tool_name: str) -> bool:
        tool = TOOLS.get(tool_name)
        return bool(tool and tool.get("requires_confirmation", False))
