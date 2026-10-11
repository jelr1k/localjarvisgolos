"""Create a bounded rollback snapshot for a JARVIS update.

Backups contain application files plus an inventory of what was copied. They
exclude large development directories and user-owned runtime data. The
inventory lets rollback remove newly installed files without clearing the
application directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import uuid


class UpdateBackupError(RuntimeError):
    """Raised when a rollback backup cannot be created safely."""


@dataclass(frozen=True)
class UpdateBackupResult:
    backup_directory: Path
    application_backup: Path
    preserved_paths: tuple[Path, ...]


INVENTORY_NAME = "application-inventory.json"
_EXCLUDED_ROOTS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "tests",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "workspace",
    "logs",
    "models",
    "node_modules",
    "user_data",
}
_EXCLUDED_FILES = {".env", ".env.local", ".env.development", ".env.production"}


class UpdateBackupService:
    """Create an isolated backup and keep the newest successful copy per install."""

    BACKUP_PREFIX = "jarvis-backup-"

    def __init__(self, backup_root: Path | None = None):
        self._backup_root = Path(backup_root).resolve() if backup_root is not None else None

    def create_backup(
        self,
        application_root: Path,
        *,
        preserve_paths: tuple[Path, ...] = (),
    ) -> UpdateBackupResult:
        root = Path(application_root).resolve()
        if not root.is_dir():
            raise UpdateBackupError("Каталог приложения для резервной копии не найден.")

        backup_root = self._resolve_backup_root(root)
        backup_root.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        unique_suffix = uuid.uuid4().hex[:8]
        backup_directory = backup_root / f"{self.BACKUP_PREFIX}{timestamp}-{unique_suffix}"
        application_backup = backup_directory / "application"

        try:
            backup_directory.mkdir(parents=True)
            inventory = self._copy_tree(
                root,
                application_backup,
                backup_root=backup_root,
                application_root=root,
            )
            (backup_directory / INVENTORY_NAME).write_text(
                json.dumps(
                    {"schema_version": 1, "files": sorted(inventory, key=str.casefold)},
                    ensure_ascii=False,
                    indent=2,
                ) + "\n",
                encoding="utf-8",
            )

            copied_preserved: list[Path] = []
            preserved_root = backup_directory / "preserved"
            for source in preserve_paths:
                source_path = Path(source).resolve()
                if not source_path.exists():
                    continue
                if source_path == backup_directory or backup_directory.is_relative_to(source_path):
                    continue
                destination = preserved_root / self._safe_name(source_path)
                if source_path.is_symlink():
                    continue
                if source_path.is_dir():
                    self._copy_external_tree(source_path, destination)
                else:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source_path, destination)
                copied_preserved.append(source_path)

            result = UpdateBackupResult(
                backup_directory=backup_directory,
                application_backup=application_backup,
                preserved_paths=tuple(copied_preserved),
            )

            # Keep the previous recovery point if this copy fails. Pruning only
            # happens after all application and explicitly preserved files were copied.
            self._remove_previous_backups(backup_root, keep=backup_directory)
            return result
        except (OSError, shutil.Error, ValueError) as exc:
            shutil.rmtree(backup_directory, ignore_errors=True)
            raise UpdateBackupError(f"Не удалось создать резервную копию: {exc}") from exc
        except Exception:
            shutil.rmtree(backup_directory, ignore_errors=True)
            raise

    def _resolve_backup_root(self, application_root: Path) -> Path:
        if self._backup_root is not None:
            return self._backup_root

        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            base = Path(local_app_data).expanduser()
        else:
            app_data = os.environ.get("APPDATA", "").strip()
            if app_data:
                base = Path(app_data).expanduser().parent / "Local"
            else:
                base = Path(tempfile.gettempdir())

        install_id = hashlib.sha256(
            str(application_root).casefold().encode("utf-8")
        ).hexdigest()[:16]
        return (base / "JARVIS" / "update-backups" / install_id).resolve()

    @staticmethod
    def _copy_tree(
        source: Path,
        destination: Path,
        *,
        backup_root: Path,
        application_root: Path,
    ) -> list[str]:
        destination.mkdir(parents=True, exist_ok=True)
        excluded = backup_root.resolve()
        inventory: list[str] = []

        def copy_directory(current_source: Path, current_destination: Path, relative_parts: tuple[str, ...]):
            for item in current_source.iterdir():
                relative = relative_parts + (item.name,)
                relative_path = Path(*relative)
                # Development trees and runtime-owned data are not part of the
                # application rollback snapshot.
                if relative[0].casefold() in {name.casefold() for name in _EXCLUDED_ROOTS}:
                    continue
                if len(relative) == 1 and item.name.casefold() in _EXCLUDED_FILES:
                    continue
                if item.is_symlink():
                    continue

                resolved = item.resolve()
                if resolved == excluded or excluded in resolved.parents:
                    continue

                target = current_destination / item.name
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    copy_directory(item, target, relative)
                elif item.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, target)
                    inventory.append(relative_path.as_posix())

        copy_directory(source, destination, ())
        return inventory

    @staticmethod
    def _copy_external_tree(source: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            if item.is_symlink():
                continue
            target = destination / item.name
            if item.is_dir():
                UpdateBackupService._copy_external_tree(item, target)
            elif item.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)

    def _remove_previous_backups(self, backup_root: Path, *, keep: Path) -> None:
        try:
            candidates = sorted(
                (
                    item
                    for item in backup_root.iterdir()
                    if item.is_dir()
                    and item.name.startswith(self.BACKUP_PREFIX)
                    and item.resolve() != keep.resolve()
                ),
                key=lambda item: item.name,
                reverse=True,
            )
            for item in candidates:
                shutil.rmtree(item)
        except (OSError, shutil.Error) as exc:
            raise UpdateBackupError(
                f"Новая резервная копия создана, но старую удалить не удалось: {exc}"
            ) from exc

    @staticmethod
    def _safe_name(path: Path) -> str:
        drive = path.drive.replace(":", "") or "root"
        parts = [part for part in path.parts if part not in (path.anchor, path.root)]
        suffix = "__".join(parts[-4:]) if parts else "root"
        return f"{drive}__{suffix}".replace(":", "_")
