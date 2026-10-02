"""Stage 16: restore the previous JARVIS installation after a failed update.

The rollback restores only application-owned files from the successful pre-update
backup. User data, workspace, logs and model caches protected by
UpdateInstallPolicy are left untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil

from services.update_install_policy import UpdateInstallPolicy


class UpdateRollbackError(RuntimeError):
    """Raised when a failed update cannot be rolled back safely."""


@dataclass(frozen=True)
class UpdateRollbackResult:
    application_root: Path
    restored_files: int
    preserved_paths: tuple[Path, ...]


class UpdateRollbackService:
    """Restore an application from its pre-update application backup."""

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
            raise UpdateRollbackError(
                "Резервная копия приложения для отката не найдена."
            )
        if not root.is_dir():
            raise UpdateRollbackError(
                "Каталог приложения для отката не найден."
            )

        install_policy = policy or UpdateInstallPolicy(root)
        if install_policy.application_root != root:
            raise UpdateRollbackError(
                "Политика отката относится к другому каталогу приложения."
            )

        try:
            for item in list(root.iterdir()):
                if install_policy.is_protected(item):
                    continue
                if item.is_dir() and not item.is_symlink():
                    shutil.rmtree(item)
                else:
                    item.unlink()

            restored = 0
            for source in backup.rglob("*"):
                relative = source.relative_to(backup)
                target = root / relative

                if install_policy.is_protected(target):
                    continue

                if source.is_symlink():
                    raise UpdateRollbackError(
                        f"Резервная копия содержит символическую ссылку: {relative}"
                    )

                if source.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                restored += 1

            return UpdateRollbackResult(
                application_root=root,
                restored_files=restored,
                preserved_paths=tuple(
                    install_policy.protected_application_paths()
                ),
            )
        except UpdateRollbackError:
            raise
        except (OSError, shutil.Error) as exc:
            raise UpdateRollbackError(
                f"Не удалось выполнить откат обновления: {exc}"
            ) from exc
