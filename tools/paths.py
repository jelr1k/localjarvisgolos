from __future__ import annotations

import os
import shutil
from pathlib import Path

from core.app_paths import APP_ROOT, WORKSPACE_DIR, ensure_application_dirs
from security.sandbox import SandboxError, is_inside_sandbox, resolve_inside_sandbox

TOOL_WORKSPACE = WORKSPACE_DIR
# Read-only search roots. Mutating tools remain restricted to WORKSPACE_DIR.
SEARCH_ROOTS = (TOOL_WORKSPACE, APP_ROOT)
SKIPPED_SEARCH_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "logs"}


def _search_roots() -> tuple[Path, ...]:
    """Возвращает актуальные read-only корни."""
    return (TOOL_WORKSPACE, APP_ROOT)


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


def is_readable_search_path(path: Path) -> bool:
    """Разрешает только существующие файлы внутри read-only search roots."""
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    if not resolved.is_file():
        return False
    for root in _search_roots():
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _clean_name(name: str) -> str:
    return str(name or "").strip().strip('"')


def _matches_name(path: Path, name: str) -> bool:
    wanted = _clean_name(name).lower()
    if not wanted:
        return False
    if path.name.lower() == wanted:
        return True
    return path.stem.lower() == Path(wanted).stem.lower()


def _iter_search_files(root: Path):
    """Идёт по разрешённым read-only корням без обхода служебных каталогов."""
    root = root.resolve()
    if not root.exists():
        return
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = [directory for directory in dirs if directory not in SKIPPED_SEARCH_DIRS]
        current_path = Path(current)
        for filename in files:
            yield current_path / filename


def find_by_name(name: str, extension: str | None = None) -> list[Path]:
    """Ищет файлы в Workspace и корне Jarvis в режиме только чтения."""
    prepare_tool_workspace()
    name = _clean_name(name)
    extension = (extension or "").strip()
    if extension and not extension.startswith("."):
        extension = "." + extension
    if not name:
        return []

    matches: list[Path] = []
    seen: set[Path] = set()
    for root in _search_roots():
        for path in _iter_search_files(root) or ():
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                continue
            if not resolved.is_file() or resolved in seen:
                continue
            if root.resolve() == TOOL_WORKSPACE.resolve() and not is_path_allowed(resolved):
                continue
            if extension and resolved.suffix.lower() != extension.lower():
                continue
            if _matches_name(resolved, name):
                seen.add(resolved)
                matches.append(resolved)
    return sorted(matches, key=lambda item: str(item).lower())


def resolve_tool_path(value: str) -> tuple[Path | None, list[Path]]:
    """Разрешает существующий файл для изменяющих file-tools только внутри workspace."""
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
    matches = [match for match in matches if is_path_allowed(match)]
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def resolve_read_path(value: str) -> tuple[Path | None, list[Path]]:
    """Разрешает существующий файл для read_file в read-only search roots."""
    raw = _clean_name(value)
    if not raw:
        return None, []

    prepare_tool_workspace()
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            return None, []
        return (resolved, [resolved]) if is_readable_search_path(resolved) else (None, [])

    try:
        workspace_candidate = resolve_inside_sandbox(candidate, allow_nonexistent=False)
        if workspace_candidate.is_file():
            return workspace_candidate, [workspace_candidate]
    except SandboxError:
        pass

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

    target = resolve_inside_sandbox(source_path.name, allow_nonexistent=True)
    if target.exists():
        raise FileExistsError(f"Файл уже существует в Workspace: {target.name}")

    try:
        shutil.copy2(source_path, target)
    except OSError as exc:
        raise OSError(f"Не удалось добавить файл в Workspace: {exc}") from exc
    return target
