import os
from pathlib import Path


def launch_application(path: str) -> dict:
    """
    Запускает приложение, файл или ярлык Windows.
    """

    if not path:
        return {
            "success": False,
            "error": "Не указан путь."
        }

    file_path = Path(path).expanduser()

    if not file_path.exists():
        return {
            "success": False,
            "error": f"Файл не найден: {file_path}"
        }

    try:
        os.startfile(str(file_path))

        return {
            "success": True,
            "message": f"Запущено: {file_path}"
        }

    except Exception as exc:
        return {
            "success": False,
            "error": f"Не удалось запустить файл: {exc}"
        }