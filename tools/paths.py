from __future__ import annotations

import shutil
from pathlib import Path

from core.app_paths import APP_ROOT, WORKSPACE_DIR, ensure_application_dirs
from security.sandbox import SandboxError, is_inside_sandbox, resolve_inside_sandbox

TOOL_WORKSPACE = WORKSPACE_DIR


def prepare_tool_workspace() -> Path:
    """Создаёт workspace относительно фактического корня Jarvis."""
    ensure_application_dirs()
    legacy_workspace = APP_ROOT / "test"
    if not TOOL_WORKSPACE.exists() and legacy_workspace.exists():
        try:
            legacy_workspace.rename(TOOL_WORKSPACE)
        except OSError:
            pass
    TOOL_WORKSPACE.mkdir(parents=True, exist_ok=True)
    return TOOL_WORKSPACE.resolve()


def is_path_allowed(path: Path) -> bool:
    return is_inside_sandbox(path, allow_nonexistent=True)


def _clean_name(name: str) -> str:
    return str(name or "").strip().strip('"')


def _matches_name(path: Path, name: str) -> bool:
    wanted = _clean_name(name).lower()
    if not wanted:
        return False
    if path.name.lower() == wanted:
        return True
    return path.stem.lower() == Path(wanted).stem.lower()


def find_by_name(name: str, extension: str | None = None) -> list[Path]:
    """Ищет файлы только внутри workspace, не выходя через ссылки наружу."""
    root = prepare_tool_workspace()
    name = _clean_name(name)
    extension = (extension or "").strip()
    if extension and not extension.startswith("."):
        extension = "." + extension
    if not name:
        return []

    matches: list[Path] = []
    for path in root.rglob("*"):
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            continue
        if not resolved.is_file() or not is_path_allowed(resolved):
            continue
        if extension and resolved.suffix.lower() != extension.lower():
            continue
        if _matches_name(resolved, name):
            matches.append(resolved)
    return sorted(set(matches), key=lambda item: str(item).lower())


def resolve_tool_path(value: str) -> tuple[Path | None, list[Path]]:
    """Разрешает существующий файл по имени, относительному или абсолютному пути."""
    raw = _clean_name(value)
    if not raw:
        return None, []

    prepare_tool_workspace()
    candidate = Path(raw).expanduser()
    try:
        if candidate.is_absolute():
            resolved = resolve_inside_sandbox(candidate, allow_nonexistent=False)
            return (resolved, [resolved]) if resolved.is_file() else (None, [])

        relative = resolve_inside_sandbox(candidate, allow_nonexistent=False)
        if relative.is_file():
            return relative, [relative]
    except SandboxError:
        return None, []

    matches = find_by_name(raw)
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def resolve_tool_target(value: str) -> Path:
    """Разрешает путь для записи/переименования/перемещения, даже если его ещё нет."""
    prepare_tool_workspace()
    return resolve_inside_sandbox(_clean_name(value), allow_nonexistent=True)


def add_file_to_workspace(source: str | Path) -> Path:
    """Копирует пользовательский файл в корень Workspace и возвращает его путь."""
    source_path = Path(source).expanduser()
    if not source_path.exists() or not source_path.is_file():
        raise ValueError("Можно добавить только существующий файл.")

    workspace = prepare_tool_workspace()
    target = resolve_inside_sandbox(source_path.name, allow_nonexistent=True)
    if target.exists():
        raise FileExistsError(f"Файл уже существует в Workspace: {target.name}")

    try:
        shutil.copy2(source_path, target)
    except OSError as exc:
        raise OSError(f"Не удалось добавить файл в Workspace: {exc}") from exc

    return target.resolve()
