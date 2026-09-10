from pathlib import Path


# Пока разрешаем удаление только из этой папки.
# Позже перенесём это в настройки JARVIS.
ALLOWED_DELETE_DIRECTORIES = [
    Path(r"C:\JARVIS\test").resolve(),
]


def _is_path_allowed(path: Path) -> bool:
    """
    Проверяет, находится ли файл внутри разрешённой папки.
    """

    path = path.resolve()

    for allowed_directory in ALLOWED_DELETE_DIRECTORIES:
        try:
            path.relative_to(allowed_directory)
            return True

        except ValueError:
            continue

    return False


def delete_file(path: str) -> dict:
    """
    Удаляет один файл.
    """

    if not path:
        return {
            "success": False,
            "error": "Не указан путь к файлу."
        }

    file_path = Path(path).expanduser()

    if not file_path.exists():
        return {
            "success": False,
            "error": f"Файл не найден: {file_path}"
        }

    if not file_path.is_file():
        return {
            "success": False,
            "error": f"Это не файл: {file_path}"
        }

    try:
        file_path = file_path.resolve()

    except OSError as exc:
        return {
            "success": False,
            "error": f"Не удалось определить путь: {exc}"
        }

    if not _is_path_allowed(file_path):
        return {
            "success": False,
            "error": (
                "Удаление из этой папки запрещено: "
                f"{file_path}"
            )
        }

    try:
        file_path.unlink()

        return {
            "success": True,
            "message": f"Файл удалён: {file_path}"
        }

    except OSError as exc:
        return {
            "success": False,
            "error": f"Не удалось удалить файл: {exc}"
        }