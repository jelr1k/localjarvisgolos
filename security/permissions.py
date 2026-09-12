from __future__ import annotations


class PermissionManager:
    """Читает разрешения инструментов из ConfigManager.

    Проверка выполняется здесь и повторно в ToolExecutor, чтобы отключение
    инструмента через UI нельзя было обойти только изменением маршрута команды.
    """

    def __init__(self, config):
        self.config = config

    def is_enabled(self, tool_name: str) -> bool:
        tools = self.config.get("tools", {})
        return bool(tools.get(tool_name, False))

    def update(self, tool_name: str, enabled: bool) -> None:
        self.config.data.setdefault("tools", {})[tool_name] = bool(enabled)
        self.config.save()
