"""Safe validation of a downloaded JARVIS update archive.

Stage 10: validate the downloaded ZIP before any installation step.
This module never extracts, installs, replaces files, or restarts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import stat
import zipfile


class UpdateValidationError(RuntimeError):
    """Raised when a downloaded update archive is not safe or valid."""


@dataclass(frozen=True)
class UpdateValidationResult:
    """Information about a validated update archive."""

    archive_path: Path
    file_count: int
    directory_count: int
    total_uncompressed_size: int


class UpdateValidator:
    """Validate a downloaded ZIP without extracting it."""

    def validate(self, archive_path: Path, expected_size: int | None = None) -> UpdateValidationResult:
        path = Path(archive_path)

        if not path.is_file():
            raise UpdateValidationError("Архив обновления не найден.")

        actual_size = path.stat().st_size
        if actual_size <= 0:
            raise UpdateValidationError("Архив обновления пуст.")

        if expected_size is not None and actual_size != expected_size:
            raise UpdateValidationError(
                f"Размер архива ({actual_size}) не совпадает с ожидаемым ({expected_size})."
            )

        try:
            with zipfile.ZipFile(path, "r") as archive:
                if archive.testzip() is not None:
                    raise UpdateValidationError("ZIP-архив повреждён: не совпадает контрольная сумма.")

                infos = archive.infolist()
                if not infos:
                    raise UpdateValidationError("ZIP-архив не содержит файлов.")

                file_count = 0
                directory_count = 0
                total_size = 0
                seen_names: set[str] = set()

                for info in infos:
                    name = info.filename.replace("\\", "/")
                    if not name or name == ".":
                        raise UpdateValidationError("ZIP-архив содержит некорректное имя записи.")

                    normalized = name.rstrip("/")
                    if normalized in {"", "."}:
                        directory_count += 1
                        continue

                    if name.startswith("/") or name.startswith("\\"):
                        raise UpdateValidationError(
                            f"ZIP-архив содержит абсолютный путь: {info.filename}"
                        )

                    parts = [part for part in normalized.split("/") if part not in ("", ".")]
                    if ".." in parts:
                        raise UpdateValidationError(
                            f"ZIP-архив содержит опасный путь: {info.filename}"
                        )

                    if normalized.lower() in seen_names:
                        raise UpdateValidationError(
                            f"ZIP-архив содержит дубликат записи: {info.filename}"
                        )
                    seen_names.add(normalized.lower())

                    mode = (info.external_attr >> 16) & 0xFFFF
                    if stat.S_ISLNK(mode):
                        raise UpdateValidationError(
                            f"ZIP-архив содержит символическую ссылку: {info.filename}"
                        )

                    if info.is_dir() or name.endswith("/"):
                        directory_count += 1
                    else:
                        file_count += 1
                        total_size += info.file_size

                if file_count == 0:
                    raise UpdateValidationError("ZIP-архив не содержит файлов для обновления.")

                return UpdateValidationResult(
                    archive_path=path,
                    file_count=file_count,
                    directory_count=directory_count,
                    total_uncompressed_size=total_size,
                )
        except UpdateValidationError:
            raise
        except (zipfile.BadZipFile, OSError, ValueError) as exc:
            raise UpdateValidationError(
                f"Не удалось проверить ZIP-архив: {exc}"
            ) from exc
