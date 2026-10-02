"""Stage 11: create a rollback backup before installing an update.

The backup is a filesystem copy. It never changes the application and does
not delete user data, configuration, logs, workspace files, or model caches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os
from pathlib import Path
import shutil
import tempfile


class UpdateBackupError(RuntimeError):
    """Raised when a rollback backup cannot be created safely."""


@dataclass(frozen=True)
class UpdateBackupResult:
    backup_directory: Path
    application_backup: Path
    preserved_paths: tuple[Path, ...]


class UpdateBackupService:
    """Create an isolated backup of the current installation."""

    def __init__(self, backup_root: Path | None = None):
        self._backup_root = Path(backup_root) if backup_root is not None else None

    def create_backup(
        self,
        application_root: Path,
        *,
        preserve_paths: tuple[Path, ...] = (),
    ) -> UpdateBackupResult:
        root = Path(application_root).resolve()
        if not root.is_dir():
            raise UpdateBackupError("Каталог приложения для резервной копии не найден.")

        backup_root = (
            self._backup_root.resolve()
            if self._backup_root is not None
            else Path(tempfile.gettempdir()).resolve() / "JARVIS-update-backups"
        )
        backup_root.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_directory = backup_root / f"jarvis-backup-{timestamp}"
        application_backup = backup_directory / "application"

        try:
            backup_directory.mkdir(parents=True)
            self._copy_tree(root, application_backup, excluded_roots=(backup_root,))

            copied_preserved: list[Path] = []
            preserved_root = backup_directory / "preserved"
            for source in preserve_paths:
                source_path = Path(source).resolve()
                if not source_path.exists():
                    continue
                if source_path == backup_directory or backup_directory.is_relative_to(source_path):
                    continue
                destination = preserved_root / self._safe_name(source_path)
                if source_path.is_dir():
                    shutil.copytree(source_path, destination, symlinks=False)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, destination)
                copied_preserved.append(source_path)

            return UpdateBackupResult(
                backup_directory=backup_directory,
                application_backup=application_backup,
                preserved_paths=tuple(copied_preserved),
            )
        except (OSError, shutil.Error) as exc:
            shutil.rmtree(backup_directory, ignore_errors=True)
            raise UpdateBackupError(f"Не удалось создать резервную копию: {exc}") from exc
        except Exception:
            shutil.rmtree(backup_directory, ignore_errors=True)
            raise

    @staticmethod
    def _copy_tree(source: Path, destination: Path, *, excluded_roots: tuple[Path, ...]) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        excluded = tuple(path.resolve() for path in excluded_roots)

        for item in source.iterdir():
            item_resolved = item.resolve()
            if any(item_resolved == path or path.is_relative_to(item_resolved) for path in excluded):
                continue
            target = destination / item.name
            if item.is_symlink():
                continue
            if item.is_dir():
                shutil.copytree(item, target, symlinks=False)
            else:
                shutil.copy2(item, target)

    @staticmethod
    def _safe_name(path: Path) -> str:
        drive = path.drive.replace(":", "") or "root"
        parts = [part for part in path.parts if part not in (path.anchor, path.root)]
        suffix = "__".join(parts[-4:]) if parts else "root"
        return f"{drive}__{suffix}".replace(":", "_")
