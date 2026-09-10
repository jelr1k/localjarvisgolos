from pathlib import Path

from tools.paths import TOOL_WORKSPACE, is_path_allowed, resolve_tool_path

ALLOWED_DELETE_DIRECTORIES = [TOOL_WORKSPACE]


def _is_path_allowed(path: Path) -> bool:
    return is_path_allowed(path)


def delete_file(path: str) -> dict:
    """Удаляет один файл только внутри workspace."""
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
        return {"success": False, "error": "Удалять можно только файлы внутри рабочей папки."}

    try:
        file_path.unlink()
        return {"success": True, "message": f"Файл удалён: {file_path}"}
    except OSError as exc:
        return {"success": False, "error": f"Не удалось удалить файл: {exc}"}
