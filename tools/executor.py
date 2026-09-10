from tools.registry import TOOLS


class ToolExecutor:

    def execute(self, tool_name: str, arguments: dict) -> dict:
        """
        Выполняет инструмент по его имени.
        """

        tool = TOOLS.get(tool_name)

        if tool is None:
            return {
                "success": False,
                "error": f"Неизвестный инструмент: {tool_name}"
            }

        function = tool["function"]

        try:
            return function(**arguments)

        except TypeError as exc:
            return {
                "success": False,
                "error": f"Неверные аргументы инструмента: {exc}"
            }

        except Exception as exc:
            return {
                "success": False,
                "error": f"Ошибка инструмента: {exc}"
            }

    def requires_confirmation(self, tool_name: str) -> bool:
        """
        Проверяет, требуется ли подтверждение пользователя.
        """

        tool = TOOLS.get(tool_name)

        if tool is None:
            return False

        return tool.get(
            "requires_confirmation",
            False
        )