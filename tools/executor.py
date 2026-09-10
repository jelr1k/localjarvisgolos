from tools.registry import TOOLS


class ToolExecutor:

    def __init__(self, enabled_tools=None):
        self.enabled_tools = set(enabled_tools) if enabled_tools is not None else set(TOOLS)

    def execute(self, tool_name: str, arguments: dict, confirmation_callback=None) -> dict:
        """Выполняет инструмент и повторно проверяет, включён ли он в настройках."""
        if tool_name not in self.enabled_tools:
            return {"success": False, "error": "Инструмент отключён в настройках JARVIS."}

        tool = TOOLS.get(tool_name)
        if tool is None:
            return {"success": False, "error": f"Неизвестный инструмент: {tool_name}"}

        if tool.get("requires_confirmation", False):
            if confirmation_callback is None:
                return {"success": False, "error": "Для этого действия требуется подтверждение пользователя."}
            if not confirmation_callback(tool_name, arguments):
                return {"success": False, "error": "Пользователь отменил действие."}

        try:
            return tool["function"](**arguments)
        except TypeError as exc:
            return {"success": False, "error": f"Неверные аргументы инструмента: {exc}"}
        except Exception as exc:
            return {"success": False, "error": f"Ошибка инструмента: {exc}"}

    def requires_confirmation(self, tool_name: str) -> bool:
        tool = TOOLS.get(tool_name)
        return bool(tool and tool.get("requires_confirmation", False))
