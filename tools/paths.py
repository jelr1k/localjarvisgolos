from pathlib import Path


TOOL_WORKSPACE = Path(r"C:\JARVIS\workspace").resolve()
LEGACY_WORKSPACE = Path(r"C:\JARVIS\test").resolve()


def prepare_tool_workspace() -> Path:
    """Создаёт workspace и при необходимости один раз переносит старую test."""
    if not TOOL_WORKSPACE.exists() and LEGACY_WORKSPACE.exists():
        try:
            LEGACY_WORKSPACE.rename(TOOL_WORKSPACE)
        except OSError:
            pass
    TOOL_WORKSPACE.mkdir(parents=True, exist_ok=True)
    return TOOL_WORKSPACE


def is_path_allowed(path: Path) -> bool:
    """Проверяет, находится ли путь внутри workspace после resolve()."""
    try:
        path.resolve().relative_to(TOOL_WORKSPACE)
        return True
    except ValueError:
        return False


def _matches_name(path: Path, name: str) -> bool:
    if path.name.lower() == name.lower():
        return True
    return not Path(name).suffix and path.stem.lower() == name.lower()


def find_by_name(name: str) -> list[Path]:
    """Рекурсивно ищет файл по имени или имени без расширения."""
    name = name.strip().strip('"')
    if not name or not TOOL_WORKSPACE.exists():
        return []

    matches = []
    for path in TOOL_WORKSPACE.rglob("*"):
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_file() and is_path_allowed(resolved) and _matches_name(resolved, name):
            matches.append(resolved)
    return sorted(set(matches), key=lambda item: str(item).lower())


def resolve_tool_path(value: str) -> tuple[Path | None, list[Path]]:
    """Разрешает абсолютный/относительный путь или простое имя файла."""
    if not value or not value.strip():
        return None, []

    prepare_tool_workspace()
    raw = value.strip().strip('"')
    candidate = Path(raw).expanduser()

    if candidate.is_absolute():
        try:
            resolved = candidate.resolve()
        except OSError:
            return None, []
        return (resolved, []) if resolved.exists() and is_path_allowed(resolved) and resolved.is_file() else (None, [])

    relative_candidate = (TOOL_WORKSPACE / candidate).resolve()
    if relative_candidate.exists() and relative_candidate.is_file() and is_path_allowed(relative_candidate):
        return relative_candidate, [relative_candidate]

    matches = find_by_name(raw)
    if len(matches) == 1:
        return matches[0], matches
    return None, matches
