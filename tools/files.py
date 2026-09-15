from __future__ import annotations

import shutil
from pathlib import Path

from security.sandbox import SandboxError, resolve_inside_sandbox
from security.validator import validate_non_empty
from tools.paths import find_by_name, prepare_tool_workspace, resolve_read_path, resolve_tool_path, resolve_tool_target

MAX_READ_BYTES = 2 * 1024 * 1024


def _result(success: bool, *, path: Path | None = None, error: str | None = None, details=None, **extra) -> dict:
    data = {"success": success}
    if path is not None:
        data["path"] = str(path)
    if error:
        data["error"] = error
    if details is not None:
        data["details"] = details
    data.update(extra)
    return data


def _existing_file(value: str) -> tuple[Path | None, list[Path], str | None]:
    try:
        raw = validate_non_empty(value, "путь к файлу")
    except ValueError as exc:
        return None, [], str(exc)
    file_path, matches = resolve_tool_path(raw)
    if len(matches) > 1:
        return None, matches, "Найдено несколько файлов с таким именем."
    if file_path is None:
        return None, [], f"Файл не найден в рабочей папке Jarvis: {raw}"
    return file_path, [file_path], None


def search_files(name: str = "", extension: str = "") -> dict:
    try:
        prepare_tool_workspace()
        matches = find_by_name(name, extension or None, fuzzy=True)
        return _result(True, details={"query": name, "count": len(matches)}, matches=[str(p) for p in matches])
    except Exception as exc:
        return _result(False, error=f"Ошибка поиска: {exc}")


def read_file(path: str) -> dict:
    try:
        raw = validate_non_empty(path, "путь к файлу")
    except ValueError as exc:
        return _result(False, error=str(exc))

    file_path, matches = resolve_read_path(raw)
    if len(matches) > 1:
        return _result(False, error="Найдено несколько файлов с таким именем.", ambiguous=True, matches=[str(p) for p in matches])
    if file_path is None:
        return _result(False, error=f"Файл не найден среди разрешённых для чтения путей: {raw}")

    try:
        size = file_path.stat().st_size
        if size > MAX_READ_BYTES:
            return _result(False, path=file_path, error=f"Файл слишком большой для чтения ({size} байт, лимит {MAX_READ_BYTES}).")
        text = file_path.read_text(encoding="utf-8")
        return _result(True, path=file_path, details={"size": size}, content=text)
    except UnicodeDecodeError:
        return _result(False, path=file_path, error="Файл не является UTF-8 текстом.")
    except OSError as exc:
        return _result(False, path=file_path, error=f"Не удалось прочитать файл: {exc}")


def create_file(path: str, content: str = "") -> dict:
    try:
        target = resolve_tool_target(validate_non_empty(path, "путь к файлу"))
        if target.exists():
            return _result(False, path=target, error="Файл уже существует.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if not target.is_file():
            return _result(False, path=target, error="Файл не был создан.")
        return _result(True, path=target, details={"bytes": target.stat().st_size})
    except (ValueError, SandboxError, OSError) as exc:
        return _result(False, error=f"Не удалось создать файл: {exc}")


def write_file(path: str, content: str) -> dict:
    try:
        target = resolve_tool_target(validate_non_empty(path, "путь к файлу"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        if not target.is_file():
            return _result(False, path=target, error="Запись не подтверждена.")
        return _result(True, path=target, details={"bytes": target.stat().st_size})
    except (ValueError, SandboxError, OSError) as exc:
        return _result(False, error=f"Не удалось записать файл: {exc}")


def delete_file(path: str) -> dict:
    """Удаляет файл и сообщает успех только после фактической проверки."""
    file_path, matches, error = _existing_file(path)
    if error:
        extra = {"ambiguous": True, "matches": [str(p) for p in matches]} if len(matches) > 1 else {}
        return _result(False, error=error, **extra)
    if file_path is None:
        return _result(False, error="Файл не найден.")
    try:
        file_path.unlink()
        if file_path.exists():
            return _result(False, path=file_path, error="Удаление не подтверждено: файл всё ещё существует.")
        return _result(True, path=file_path, details={"deleted": True})
    except PermissionError as exc:
        return _result(False, path=file_path, error=f"Нет прав на удаление: {exc}")
    except OSError as exc:
        return _result(False, path=file_path, error=f"Не удалось удалить файл: {exc}")


def rename_file(path: str, new_name: str) -> dict:
    file_path, matches, error = _existing_file(path)
    if error:
        extra = {"ambiguous": True, "matches": [str(p) for p in matches]} if len(matches) > 1 else {}
        return _result(False, error=error, **extra)
    try:
        new_name = validate_non_empty(new_name, "новое имя")
        if Path(new_name).name != new_name:
            return _result(False, error="Новое имя должно быть именем файла без пути.")
        target = resolve_inside_sandbox(file_path.parent / new_name, allow_nonexistent=True)
        file_path.rename(target)
        return _result(target.exists(), path=target, error=None if target.exists() else "Переименование не подтверждено.")
    except (ValueError, SandboxError, OSError) as exc:
        return _result(False, error=f"Не удалось переименовать файл: {exc}")


def copy_file(path: str, destination: str) -> dict:
    source, matches, error = _existing_file(path)
    if error:
        extra = {"ambiguous": True, "matches": [str(p) for p in matches]} if len(matches) > 1 else {}
        return _result(False, error=error, **extra)
    try:
        target = resolve_tool_target(validate_non_empty(destination, "назначение"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return _result(target.is_file(), path=target, error=None if target.is_file() else "Копирование не подтверждено.")
    except (ValueError, SandboxError, OSError) as exc:
        return _result(False, error=f"Не удалось скопировать файл: {exc}")


def move_file(path: str, destination: str) -> dict:
    source, matches, error = _existing_file(path)
    if error:
        extra = {"ambiguous": True, "matches": [str(p) for p in matches]} if len(matches) > 1 else {}
        return _result(False, error=error, **extra)
    try:
        target = resolve_tool_target(validate_non_empty(destination, "назначение"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return _result(target.is_file() and not source.exists(), path=target, error=None if target.is_file() and not source.exists() else "Перемещение не подтверждено.")
    except (ValueError, SandboxError, OSError) as exc:
        return _result(False, error=f"Не удалось переместить файл: {exc}")


def create_folder(path: str) -> dict:
    try:
        target = resolve_tool_target(validate_non_empty(path, "путь к папке"))
        target.mkdir(parents=True, exist_ok=False)
        return _result(target.is_dir(), path=target, error=None if target.is_dir() else "Папка не была создана.")
    except FileExistsError:
        return _result(False, error="Папка уже существует.")
    except (ValueError, SandboxError, OSError) as exc:
        return _result(False, error=f"Не удалось создать папку: {exc}")


def file_info(path: str) -> dict:
    file_path, matches, error = _existing_file(path)
    if error:
        extra = {"ambiguous": True, "matches": [str(p) for p in matches]} if len(matches) > 1 else {}
        return _result(False, error=error, **extra)
    try:
        stat = file_path.stat()
        return _result(True, path=file_path, details={
            "name": file_path.name,
            "extension": file_path.suffix,
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "is_file": file_path.is_file(),
        })
    except OSError as exc:
        return _result(False, path=file_path, error=f"Не удалось получить информацию: {exc}")
