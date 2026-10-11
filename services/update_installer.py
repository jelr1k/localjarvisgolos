"""Transactional installation of a validated JARVIS update archive.

Only files listed in the updater's own manifest are eligible for stale-file
removal. Unmanaged files (for example .git, .venv, tests and personal notes)
are never deleted just because they were absent from the release ZIP.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import uuid
import zipfile

from services.update_install_policy import UpdateInstallPolicy
from services.update_validator import UpdateValidationError, UpdateValidator


MANIFEST_NAME = ".jarvis-update-manifest.json"
MANIFEST_SCHEMA = 1


class UpdateInstallError(RuntimeError):
    """Raised when an update cannot be installed safely."""


@dataclass(frozen=True)
class UpdateInstallResult:
    application_root: Path
    installed_files: int
    preserved_paths: tuple[Path, ...]


class UpdateInstaller:
    """Install a ZIP transactionally while preserving unmanaged application data."""

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

        if self._staging_root is not None and (
            self._staging_root == root or root in self._staging_root.parents
        ):
            raise UpdateInstallError("Временный каталог установки не должен находиться внутри приложения.")

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
                staging / "transaction-backup",
            )
            preserved = tuple(install_policy.protected_application_paths())
            return UpdateInstallResult(
                application_root=root,
                installed_files=installed_files,
                preserved_paths=preserved,
            )
        except UpdateInstallError:
            raise
        except (OSError, shutil.Error, zipfile.BadZipFile, ValueError) as exc:
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
                    if relative == PurePosixPath("."):
                        continue

                    mode = (info.external_attr >> 16) & 0xFFFF
                    if stat.S_ISLNK(mode):
                        raise UpdateInstallError(
                            f"Архив содержит символическую ссылку: {info.filename}"
                        )

                    target = destination.joinpath(*relative.parts)
                    try:
                        target.resolve().relative_to(destination.resolve())
                    except ValueError as exc:
                        raise UpdateInstallError(
                            f"Архив выходит за пределы временного каталога: {info.filename}"
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

        reserved_windows_names = {
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }
        for part in parts:
            if (
                any(char in part for char in '<>:"|?*')
                or part.endswith((".", " "))
                or part.split(".", 1)[0].upper() in reserved_windows_names
            ):
                return None
        return PurePosixPath(*parts)

    @staticmethod
    def _find_payload_root(extracted_root: Path) -> Path:
        children = list(extracted_root.iterdir())
        files = [item for item in children if item.is_file()]
        directories = [item for item in children if item.is_dir()]

        if files and directories:
            return extracted_root
        if len(directories) == 1 and not files:
            return directories[0]
        if len(directories) > 1:
            return extracted_root
        if files:
            return extracted_root
        raise UpdateInstallError("В архиве не найдено содержимое приложения.")

    def _replace_application_files(
        self,
        source_root: Path,
        destination_root: Path,
        policy: UpdateInstallPolicy,
        transaction_backup: Path,
    ) -> int:
        manifest_path = destination_root / MANIFEST_NAME
        if manifest_path.is_symlink() or (manifest_path.exists() and not manifest_path.is_file()):
            raise UpdateInstallError("Файл манифеста обновления повреждён или является ссылкой.")

        old_managed = self._read_manifest(manifest_path)
        incoming: dict[str, Path] = {}

        for source in source_root.rglob("*"):
            if source.is_symlink():
                raise UpdateInstallError(
                    f"Распакованное обновление содержит символическую ссылку: {source.relative_to(source_root)}"
                )
            if not source.is_file():
                continue

            relative = source.relative_to(source_root).as_posix()
            if relative.casefold() == MANIFEST_NAME.casefold():
                raise UpdateInstallError(
                    f"Архив не должен содержать зарезервированный файл {MANIFEST_NAME}."
                )

            target = self._safe_target(destination_root, relative)
            if policy.is_protected(target):
                continue
            if relative.casefold() in {name.casefold() for name in incoming}:
                raise UpdateInstallError(f"Обновление содержит повторяющийся путь: {relative}")
            self._preflight_target(destination_root, target, relative)
            incoming[relative] = source

        new_names = {name.casefold() for name in incoming}
        obsolete = [
            name for name in old_managed
            if name.casefold() not in new_names and not policy.is_protected(
                self._safe_target(destination_root, name)
            )
        ]

        # Validate every target before touching the installation.
        touched: dict[str, Path] = {}
        for relative in [*incoming.keys(), *obsolete]:
            target = self._safe_target(destination_root, relative)
            self._preflight_target(destination_root, target, relative, allow_missing_obsolete=True)
            touched[relative] = target

        if manifest_path.exists():
            if manifest_path.is_symlink() or not manifest_path.is_file():
                raise UpdateInstallError("Невозможно безопасно заменить манифест обновления.")
        else:
            self._preflight_target(destination_root, manifest_path, MANIFEST_NAME)
        touched[MANIFEST_NAME] = manifest_path

        transaction_backup.mkdir(parents=True, exist_ok=True)
        snapshot_map: dict[str, Path | None] = {}
        for relative, target in touched.items():
            if target.is_file():
                snapshot = transaction_backup.joinpath(*PurePosixPath(relative).parts)
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, snapshot)
                snapshot_map[relative] = snapshot
            else:
                snapshot_map[relative] = None

        try:
            for relative in obsolete:
                target = touched[relative]
                if target.is_file():
                    target.unlink()

            for relative, source in sorted(incoming.items()):
                target = touched[relative]
                target.parent.mkdir(parents=True, exist_ok=True)
                temp_target = target.with_name(f".{target.name}.jarvis-{uuid.uuid4().hex}.tmp")
                try:
                    shutil.copy2(source, temp_target)
                    os.replace(temp_target, target)
                finally:
                    try:
                        temp_target.unlink(missing_ok=True)
                    except OSError:
                        pass

            payload = {
                "schema_version": MANIFEST_SCHEMA,
                "files": sorted(incoming, key=str.casefold),
            }
            manifest_temp = manifest_path.with_name(
                f".{MANIFEST_NAME}.{uuid.uuid4().hex}.tmp"
            )
            try:
                manifest_temp.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                os.replace(manifest_temp, manifest_path)
            finally:
                try:
                    manifest_temp.unlink(missing_ok=True)
                except OSError:
                    pass
        except Exception as exc:
            restore_errors: list[str] = []
            for relative, snapshot in reversed(list(snapshot_map.items())):
                target = touched[relative]
                try:
                    if target.is_symlink():
                        target.unlink()
                    elif target.is_file():
                        target.unlink()
                    elif target.exists():
                        raise OSError("путь неожиданно стал каталогом")

                    if snapshot is not None and snapshot.is_file():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(snapshot, target)
                    self._prune_empty_parents(target.parent, destination_root)
                except OSError as restore_error:
                    restore_errors.append(f"{relative}: {restore_error}")

            suffix = (
                " Не все изменения удалось восстановить: " + "; ".join(restore_errors)
                if restore_errors else ""
            )
            raise UpdateInstallError(
                f"Установка прервана; выполнено локальное восстановление файлов: {exc}.{suffix}"
            ) from exc

        return len(incoming)

    @classmethod
    def _read_manifest(cls, path: Path) -> list[str]:
        if not path.exists():
            return []
        if path.is_symlink() or not path.is_file():
            raise UpdateInstallError("Манифест предыдущей версии небезопасен.")

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise UpdateInstallError(f"Не удалось прочитать манифест предыдущей версии: {exc}") from exc

        if not isinstance(data, dict) or data.get("schema_version") != MANIFEST_SCHEMA:
            raise UpdateInstallError("Манифест предыдущей версии имеет неподдерживаемый формат.")
        files = data.get("files")
        if not isinstance(files, list) or not all(isinstance(item, str) for item in files):
            raise UpdateInstallError("Манифест предыдущей версии содержит некорректный список файлов.")

        result: list[str] = []
        seen: set[str] = set()
        for name in files:
            safe = cls._safe_member_path(name)
            if safe is None or safe == PurePosixPath(".") or safe.as_posix().casefold() == MANIFEST_NAME.casefold():
                raise UpdateInstallError(f"Манифест содержит небезопасный путь: {name!r}")
            normalized = safe.as_posix()
            folded = normalized.casefold()
            if folded in seen:
                raise UpdateInstallError(f"Манифест содержит повторяющийся путь: {normalized}")
            seen.add(folded)
            result.append(normalized)
        return result

    @classmethod
    def _safe_target(cls, root: Path, relative: str) -> Path:
        safe = cls._safe_member_path(relative)
        if safe is None or safe == PurePosixPath("."):
            raise UpdateInstallError(f"Небезопасный путь файла обновления: {relative!r}")

        target = root.joinpath(*safe.parts)
        try:
            target.resolve(strict=False).relative_to(root.resolve())
        except ValueError as exc:
            raise UpdateInstallError(f"Путь выходит за пределы приложения: {relative}") from exc

        current = root
        for part in safe.parts:
            current = current / part
            if current.is_symlink():
                raise UpdateInstallError(f"Нельзя обновлять путь через символическую ссылку: {relative}")
        return target

    @classmethod
    def _preflight_target(
        cls,
        root: Path,
        target: Path,
        relative: str,
        *,
        allow_missing_obsolete: bool = False,
    ) -> None:
        current = root
        try:
            parts = target.relative_to(root).parts
        except ValueError as exc:
            raise UpdateInstallError(f"Путь выходит за пределы приложения: {relative}") from exc

        for part in parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise UpdateInstallError(f"Путь обновления проходит через ссылку: {relative}")
            if current.exists() and not current.is_dir():
                raise UpdateInstallError(f"Родительский путь файла не является каталогом: {relative}")

        if target.is_symlink():
            raise UpdateInstallError(f"Нельзя заменить символическую ссылку: {relative}")
        if target.exists() and target.is_dir() and not allow_missing_obsolete:
            raise UpdateInstallError(
                f"Невозможно заменить файл обновления: на его месте каталог {relative}"
            )
        if target.exists() and target.is_dir() and allow_missing_obsolete:
            raise UpdateInstallError(
                f"Манифест считает путь файлом, но на его месте каталог: {relative}"
            )

    @staticmethod
    def _prune_empty_parents(directory: Path, root: Path) -> None:
        root = root.resolve()
        current = directory
        while current != root and root in current.parents:
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
