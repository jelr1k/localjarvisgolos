from tools.applications import launch_application
from tools.files import delete_file


TOOLS = {
    "launch_application": {
        "function": launch_application,
        "description": (
            "Запускает приложение, файл или ярлык Windows."
        ),
        "parameters": {
            "path": "Полный путь к файлу или ярлыку."
        },
        "requires_confirmation": False,
    },

    "delete_file": {
        "function": delete_file,
        "description": (
            "Удаляет один файл."
        ),
        "parameters": {
            "path": "Полный путь к файлу."
        },
        "requires_confirmation": True,
    },
}