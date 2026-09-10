from tools.applications import launch_application
from tools.files import delete_file
from tools.paths import TOOL_WORKSPACE


TOOLS = {
    "launch_application": {
        "function": launch_application,
        "description": (
            f"Запускает любой файл Windows из папки {TOOL_WORKSPACE} "
            "или её подпапок. Пользователь может указать просто имя файла, "
            "например Minecraft.exe; полный путь не нужен. Если найдено "
            "несколько одинаковых имён, не выбирай сам — сообщи пользователю "
            "варианты и попроси уточнить. Никогда не запускай файл вне этой папки."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Имя файла, относительный путь внутри рабочей папки или полный путь внутри неё."
                }
            },
            "required": ["path"]
        },
        "requires_confirmation": False,
    },

    "delete_file": {
        "function": delete_file,
        "description": (
            f"Удаляет один файл только из папки {TOOL_WORKSPACE} или её подпапок. "
            "Пользователь может написать просто имя файла, например test.txt; "
            "полный путь не нужен. Если найдено несколько файлов с таким именем, "
            "не выбирай сам — попроси пользователя уточнить. Папки удалять нельзя. "
            "Перед удалением требуется подтверждение пользователя. Никогда не удаляй "
            "файлы вне рабочей папки."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Имя файла, относительный путь внутри рабочей папки или полный путь внутри неё."
                }
            },
            "required": ["path"]
        },
        "requires_confirmation": True,
    },
}


def ollama_tools(enabled_tools=None) -> list[dict]:
    """Возвращает включённые инструменты в формате Ollama tool calling."""
    names = set(enabled_tools) if enabled_tools is not None else set(TOOLS)
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for name, tool in TOOLS.items()
        if name in names
    ]
