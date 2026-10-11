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
    """Validate a ZIP with bounded metadata before decompressing its contents."""

    def __init__(
        self,
        *,
        max_entries: int = 10_000,
        max_total_uncompressed_size: int = 512 * 1024 * 1024,
        max_entry_size: int = 256 * 1024 * 1024,
        max_compression_ratio: float = 1000.0,
    ):
        if max_entries <= 0 or max_total_uncompressed_size <= 0 or max_entry_size <= 0:
            raise ValueError("Ограничения архива должны быть больше нуля.")
        if max_compression_ratio <= 1:
            raise ValueError("Допустимый коэффициент сжатия должен быть больше 1.")
        self._max_entries = int(max_entries)
        self._max_total_uncompressed_size = int(max_total_uncompressed_size)
        self._max_entry_size = int(max_entry_size)
        self._max_compression_ratio = float(max_compression_ratio)

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
                infos = archive.infolist()
                if not infos:
                    raise UpdateValidationError("ZIP-архив не содержит файлов.")
                if len(infos) > self._max_entries:
                    raise UpdateValidationError(
                        f"ZIP-архив содержит слишком много записей ({len(infos)})."
                    )

                # Check declared expansion limits before testzip() decompresses data.
                declared_total = 0
                for info in infos:
                    if info.file_size < 0 or info.compress_size < 0:
                        raise UpdateValidationError("ZIP-архив содержит некорректные размеры.")
                    if info.file_size > self._max_entry_size:
                        raise UpdateValidationError(
                            f"Файл в ZIP превышает допустимый размер: {info.filename}"
                        )
                    declared_total += info.file_size
                    if declared_total > self._max_total_uncompressed_size:
                        raise UpdateValidationError(
                            "Суммарный распакованный размер ZIP превышает допустимый лимит."
                        )
                    if info.file_size > 0:
                        if info.compress_size == 0:
                            raise UpdateValidationError(
                                f"ZIP-архив содержит подозрительную степень сжатия: {info.filename}"
                            )
                        ratio = info.file_size / info.compress_size
                        if ratio > self._max_compression_ratio:
                            raise UpdateValidationError(
                                f"Слишком высокая степень сжатия файла в ZIP: {info.filename}"
                            )

                if archive.testzip() is not None:
                    raise UpdateValidationError("ZIP-архив повреждён: не совпадает контрольная сумма.")

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
