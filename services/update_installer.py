"""Stage 13: install a previously validated JARVIS update safely.

The installer works from a validated ZIP and a prepared application directory.
It extracts into a private staging directory first, then replaces only
application-owned files. User data, logs, workspace files and external model
caches described by UpdateInstallPolicy are never removed or overwritten.

This service does not restart JARVIS. A future standalone updater process must
call it after the main application has exited.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile

from services.update_install_policy import UpdateInstallPolicy
from services.update_validator import UpdateValidationError, UpdateValidator


class UpdateInstallError(RuntimeError):
    """Raised when an update cannot be installed safely."""


@dataclass(frozen=True)
class UpdateInstallResult:
    application_root: Path
    installed_files: int
    preserved_paths: tuple[Path, ...]


class UpdateInstaller:
    """Install a validated ZIP while preserving user-owned paths."""

    def __init__(
        self,
        *,
        validator: UpdateValidator | None = None,
        staging_root: Path | None = None,
    ):
        self._validator = validator or UpdateValidator()
        self._staging_root = Path(staging_root).resolve() if staging_root is not None else None

    def install(
        self,
        archive_path: Path,
        application_root: Path,
        *,
        policy: UpdateInstallPolicy | None = None,
        expected_size: int | None = None,
    ) -> UpdateInstallResult:
        archive = Path(archive_path).resolve()
        root = Path(application_root).resolve()

        if not root.is_dir():
            raise UpdateInstallError("Каталог приложения для установки не найден.")

        if not archive.is_file():
            raise UpdateInstallError("Архив обновления не найден.")

        install_policy = policy or UpdateInstallPolicy(root)
        if install_policy.application_root != root:
            raise UpdateInstallError("Политика обновления относится к другому каталогу приложения.")

        try:
            self._validator.validate(archive, expected_size=expected_size)
        except UpdateValidationError as exc:
            raise UpdateInstallError(f"Архив не прошёл повторную проверку: {exc}") from exc

        staging = Path(
            tempfile.mkdtemp(
                prefix="jarvis-install-",
                dir=str(self._staging_root) if self._staging_root else None,
            )
        )

        try:
            extracted_root = staging / "payload"
            self._extract_archive(archive, extracted_root)
            source_root = self._find_payload_root(extracted_root)
            installed_files = self._replace_application_files(
                source_root,
                root,
                install_policy,
            )
            preserved = tuple(install_policy.protected_application_paths())
            return UpdateInstallResult(
                application_root=root,
                installed_files=installed_files,
                preserved_paths=preserved,
            )
        except UpdateInstallError:
            raise
        except (OSError, shutil.Error, zipfile.BadZipFile) as exc:
            raise UpdateInstallError(f"Не удалось установить обновление: {exc}") from exc
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _extract_archive(self, archive: Path, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(archive, "r") as zf:
                infos = zf.infolist()
                if not infos:
                    raise UpdateInstallError("Архив обновления пуст.")

                for info in infos:
                    relative = self._safe_member_path(info.filename)
                    if relative is None:
                        raise UpdateInstallError(
                            f"Архив содержит небезопасный путь: {info.filename}"
                        )

                    mode = (info.external_attr >> 16) & 0xFFFF
                    if stat.S_ISLNK(mode):
                        raise UpdateInstallError(
                            f"Архив содержит символическую ссылку: {info.filename}"
                        )

                    target = destination.joinpath(*relative.parts)
                    target_resolved = target.resolve()
                    try:
                        target_resolved.relative_to(destination.resolve())
                    except ValueError as exc:
                        raise UpdateInstallError(
                            f"Архив выходит за пределы каталога установки: {info.filename}"
                        ) from exc

                    if info.is_dir() or info.filename.endswith(("/", "\\")):
                        target.mkdir(parents=True, exist_ok=True)
                        continue

                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info, "r") as source, target.open("wb") as output:
                        shutil.copyfileobj(source, output, length=1024 * 1024)
        except UpdateInstallError:
            raise
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            raise UpdateInstallError(f"Не удалось распаковать архив обновления: {exc}") from exc

    @staticmethod
    def _safe_member_path(name: str) -> PurePosixPath | None:
        normalized = str(name).replace("\\", "/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts:
            return None
        parts = tuple(part for part in path.parts if part not in ("", "."))
        if not parts:
            return PurePosixPath(".")
        return PurePosixPath(*parts)

    @staticmethod
    def _find_payload_root(extracted_root: Path) -> Path:
        children = [item for item in extracted_root.iterdir()]
        files = [item for item in children if item.is_file()]
        directories = [item for item in children if item.is_dir()]

        if files and directories:
            return extracted_root
        if len(directories) == 1 and not files:
            return directories[0]
        if len(directories) > 1:
            return extracted_root
        raise UpdateInstallError("В архиве не найдено содержимое приложения.")

    def _replace_application_files(
        self,
        source_root: Path,
        destination_root: Path,
        policy: UpdateInstallPolicy,
    ) -> int:
        installed = 0

        for item in list(destination_root.iterdir()):
            if policy.is_protected(item):
                continue
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink()

        for source in source_root.rglob("*"):
            relative = source.relative_to(source_root)
            target = destination_root / relative
            if policy.is_protected(target):
                continue

            if source.is_symlink():
                raise UpdateInstallError(
                    f"Распакованное обновление содержит символическую ссылку: {relative}"
                )

            if source.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            installed += 1

        return installed
