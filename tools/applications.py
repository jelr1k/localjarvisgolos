import os
from pathlib import Path

from tools.paths import TOOL_WORKSPACE, is_path_allowed, resolve_tool_path

ALLOWED_APPLICATION_DIRECTORY = TOOL_WORKSPACE


def _is_allowed_application(path: Path) -> bool:
    return is_path_allowed(path)


def launch_application(path: str) -> dict:
    """Открывает/запускает любой файл или ярлык из workspace."""
    if not path:
        return {"success": False, "error": "Не указан путь к файлу."}

    file_path, matches = resolve_tool_path(path)
    if len(matches) > 1:
        return {
            "success": False,
            "error": "Найдено несколько файлов с таким именем.",
            "ambiguous": True,
            "matches": [str(item) for item in matches],
        }
    if file_path is None:
        return {"success": False, "error": f"Файл не найден в рабочей папке JARVIS: {path}"}
    if not file_path.is_file() or not is_path_allowed(file_path):
        return {"success": False, "error": "Открывать можно только файлы внутри рабочей папки."}

    try:
        # Windows сам обработает .lnk, .exe, .bat, .cmd и обычные ассоциированные файлы.
        os.startfile(str(file_path))
        return {"success": True, "message": f"Запущено: {file_path}"}
    except OSError as exc:
        return {"success": False, "error": f"Не удалось запустить файл: {exc}"}
