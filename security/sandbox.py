from __future__ import annotations

from pathlib import Path

from core.app_paths import WORKSPACE_DIR, ensure_application_dirs


class SandboxError(ValueError):
    """Ошибка выхода за пределы разрешённой рабочей папки."""


def sandbox_root() -> Path:
    ensure_application_dirs()
    return WORKSPACE_DIR.resolve()


def resolve_inside_sandbox(value: str | Path, *, allow_nonexistent: bool = True) -> Path:
    """Нормализует путь и гарантирует, что он находится внутри sandbox.

    По умолчанию разрешает ещё не существующий конечный путь, сохраняя
    проверку фактического расположения существующих родительских каталогов.
    Для операций, которым нужен существующий объект, передаётся
    ``allow_nonexistent=False``.
    """
    if value is None or not str(value).strip():
        raise SandboxError("Путь не указан.")

    root = sandbox_root()
    raw = Path(str(value).strip().strip('"')).expanduser()
    candidate = raw if raw.is_absolute() else root / raw

    try:
        resolved = candidate.resolve(strict=not allow_nonexistent)
    except OSError as exc:
        raise SandboxError(f"Не удалось разрешить путь: {exc}") from exc

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SandboxError("Путь находится вне рабочей папки Jarvis.") from exc

    return resolved


def is_inside_sandbox(value: str | Path, *, allow_nonexistent: bool = True) -> bool:
    try:
        resolve_inside_sandbox(value, allow_nonexistent=allow_nonexistent)
        return True
    except (SandboxError, OSError, ValueError):
        return False
