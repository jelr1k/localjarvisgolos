"""Conservative rollback for a failed JARVIS update.

Rollback restores files present in the pre-update snapshot and removes only
new files recorded as updater-managed. It never clears the application root.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import shutil

from services.update_install_policy import UpdateInstallPolicy


MANIFEST_NAME = ".jarvis-update-manifest.json"
INVENTORY_NAME = "application-inventory.json"
_UNMANAGED_ROOTS = {
    ".git", ".github", ".venv", "venv", "env", "tests",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", "__pycache__",
    "workspace", "logs", "models", "node_modules",
}


class UpdateRollbackError(RuntimeError):
    """Raised when a failed update cannot be rolled back safely."""


@dataclass(frozen=True)
class UpdateRollbackResult:
    application_root: Path
    restored_files: int
    preserved_paths: tuple[Path, ...]


class UpdateRollbackService:
    """Restore an application from a pre-update backup without clearing root data."""

    def restore(
        self,
        backup_application: Path,
        application_root: Path,
        *,
        policy: UpdateInstallPolicy | None = None,
    ) -> UpdateRollbackResult:
        backup = Path(backup_application).resolve()
        root = Path(application_root).resolve()

        if not backup.is_dir():
            raise UpdateRollbackError("Резервная копия приложения для отката не найдена.")
        if not root.is_dir():
            raise UpdateRollbackError("Каталог приложения для отката не найден.")

        install_policy = policy or UpdateInstallPolicy(root)
        if install_policy.application_root != root:
            raise UpdateRollbackError("Политика отката относится к другому каталогу приложения.")

        try:
            backup_files = self._read_backup_inventory(backup)
            current_managed = self._read_current_manifest(root)
            backup_keys = {name.casefold() for name in backup_files}

            # Preflight every source and destination before changing anything.
            restore_items: list[tuple[Path, Path, str]] = []
            for source in backup.rglob("*"):
                if source.is_symlink():
                    raise UpdateRollbackError(
                        f"Резервная копия содержит символическую ссылку: {source.relative_to(backup)}"
                    )
                if not source.is_file():
                    continue
                relative = source.relative_to(backup).as_posix()
                if not self._should_restore(relative):
                    continue
                target = self._safe_target(root, relative)
                if install_policy.is_protected(target):
                    continue
                if target.exists() and target.is_dir():
                    raise UpdateRollbackError(
                        f"Невозможно восстановить файл: на его месте каталог {relative}"
                    )
                restore_items.append((source, target, relative))

            removals: list[tuple[str, Path]] = []
            for relative in current_managed:
                if relative.casefold() in backup_keys:
                    continue
                if not self._should_restore(relative):
                    continue
                target = self._safe_target(root, relative)
                if install_policy.is_protected(target):
                    continue
                if target.exists() and target.is_dir():
                    raise UpdateRollbackError(
                        f"Манифест считает путь файлом, но на его месте каталог: {relative}"
                    )
                removals.append((relative, target))

            manifest_path = root / MANIFEST_NAME
            had_old_manifest = MANIFEST_NAME.casefold() in backup_keys
            if manifest_path.is_symlink() or (
                manifest_path.exists() and not manifest_path.is_file()
            ):
                raise UpdateRollbackError("Текущий манифест обновления небезопасен.")

            for _, target in removals:
                if target.is_symlink():
                    raise UpdateRollbackError(f"Нельзя удалить символическую ссылку: {target}")

            for _, target, relative in restore_items:
                self._safe_target(root, relative)
                if target.is_symlink():
                    raise UpdateRollbackError(f"Нельзя заменить символическую ссылку: {relative}")

            # Remove only updater-managed files created after the backup.
            for _, target in removals:
                if target.is_file():
                    target.unlink()

            restored = 0
            for source, target, _ in restore_items:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                restored += 1

            # A legacy installation may not have had a manifest. Do not leave
            # the failed update's manifest behind in that case.
            if not had_old_manifest and manifest_path.is_file():
                manifest_path.unlink()

            return UpdateRollbackResult(
                application_root=root,
                restored_files=restored,
                preserved_paths=tuple(install_policy.protected_application_paths()),
            )
        except UpdateRollbackError:
            raise
        except (OSError, shutil.Error, ValueError, json.JSONDecodeError) as exc:
            raise UpdateRollbackError(f"Не удалось выполнить откат обновления: {exc}") from exc

    @classmethod
    def _read_backup_inventory(cls, backup: Path) -> list[str]:
        inventory_path = backup.parent / INVENTORY_NAME
        if inventory_path.is_file():
            try:
                payload = json.loads(inventory_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise UpdateRollbackError(f"Не удалось прочитать инвентарь резервной копии: {exc}") from exc
            if (
                not isinstance(payload, dict)
                or payload.get("schema_version") != 1
                or not isinstance(payload.get("files"), list)
                or not all(isinstance(item, str) for item in payload["files"])
            ):
                raise UpdateRollbackError("Инвентарь резервной копии имеет некорректный формат.")
            return [cls._normalize_relative(item) for item in payload["files"]]

        # Compatibility with backups produced by older JARVIS versions.
        # Legacy backups may be larger, but they still must not cause root-wide deletion.
        result = []
        for source in backup.rglob("*"):
            if source.is_symlink():
                continue
            if source.is_file():
                relative = source.relative_to(backup).as_posix()
                if cls._should_restore(relative):
                    result.append(cls._normalize_relative(relative))
        return result

    @classmethod
    def _read_current_manifest(cls, root: Path) -> list[str]:
        path = root / MANIFEST_NAME
        if not path.exists():
            return []
        if path.is_symlink() or not path.is_file():
            raise UpdateRollbackError("Текущий манифест обновления небезопасен.")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise UpdateRollbackError(f"Не удалось прочитать текущий манифест: {exc}") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or not isinstance(payload.get("files"), list)
            or not all(isinstance(item, str) for item in payload["files"])
        ):
            raise UpdateRollbackError("Текущий манифест обновления имеет некорректный формат.")
        return [cls._normalize_relative(item) for item in payload["files"]]

    @staticmethod
    def _normalize_relative(value: str) -> str:
        normalized = str(value).replace("\\", "/")
        path = PurePosixPath(normalized)
        if (
            not normalized
            or path.is_absolute()
            or ".." in path.parts
            or any(char in part for part in path.parts for char in '<>:"|?*')
        ):
            raise UpdateRollbackError(f"Инвентарь содержит небезопасный путь: {value!r}")
        parts = tuple(part for part in path.parts if part not in ("", "."))
        if not parts:
            raise UpdateRollbackError(f"Инвентарь содержит пустой путь: {value!r}")
        return PurePosixPath(*parts).as_posix()

    @staticmethod
    def _should_restore(relative: str) -> bool:
        parts = PurePosixPath(relative.replace("\\", "/")).parts
        if not parts:
            return False
        if parts[0].casefold() in {name.casefold() for name in _UNMANAGED_ROOTS}:
            return False
        return True

    @classmethod
    def _safe_target(cls, root: Path, relative: str) -> Path:
        normalized = cls._normalize_relative(relative)
        target = root.joinpath(*PurePosixPath(normalized).parts)
        try:
            target.resolve(strict=False).relative_to(root.resolve())
        except ValueError as exc:
            raise UpdateRollbackError(f"Путь выходит за пределы приложения: {relative}") from exc

        current = root
        for part in PurePosixPath(normalized).parts:
            current = current / part
            if current.is_symlink():
                raise UpdateRollbackError(f"Нельзя работать через символическую ссылку: {relative}")
        return target
