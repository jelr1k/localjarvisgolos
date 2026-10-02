"""Safe staged updater download service for JARVIS.

Stage 9: download a validated update archive into an isolated temporary
directory. This module never extracts, installs, replaces files, or restarts
the application.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
import time

import requests

from services.update_service import UpdatePlan, UpdateServiceError, suggested_archive_path


class UpdateDownloadError(RuntimeError):
    """Raised when an update archive cannot be downloaded safely."""


@dataclass(frozen=True)
class UpdateDownloadResult:
    """Information about a successfully downloaded temporary archive."""

    archive_path: Path
    temp_directory: Path
    bytes_downloaded: int
    expected_size: int


class UpdateDownloader:
    """Stream a validated update archive into an isolated temporary directory."""

    def __init__(
        self,
        *,
        temp_root: Path | None = None,
        timeout: tuple[float, float] = (10.0, 60.0),
        chunk_size: int = 1024 * 1024,
        max_size: int = 2 * 1024 * 1024 * 1024,
        session=None,
    ):
        if chunk_size <= 0:
            raise ValueError("Размер блока загрузки должен быть больше нуля.")
        if max_size <= 0:
            raise ValueError("Максимальный размер архива должен быть больше нуля.")

        self._temp_root = Path(temp_root) if temp_root is not None else None
        self._timeout = timeout
        self._chunk_size = chunk_size
        self._max_size = max_size
        self._session = session or requests.Session()

    def download(self, plan: UpdatePlan, progress_callback=None) -> UpdateDownloadResult:
        """Download the update archive without extracting or installing it."""
        self._validate_plan(plan)

        temp_directory = Path(
            tempfile.mkdtemp(prefix="jarvis-update-", dir=str(self._temp_root) if self._temp_root else None)
        )
        archive_path = suggested_archive_path(temp_directory, plan)

        try:
            response = self._session.get(
                plan.download_url,
                stream=True,
                timeout=self._timeout,
            )
            response.raise_for_status()

            content_length = self._content_length(response)
            if content_length is not None and content_length > self._max_size:
                raise UpdateDownloadError("Размер архива превышает допустимый лимит.")
            if content_length is not None and content_length != plan.asset_size:
                raise UpdateDownloadError(
                    f"Размер архива на сервере ({content_length}) не совпадает "
                    f"с размером релиза ({plan.asset_size})."
                )

            total = content_length or plan.asset_size
            downloaded = 0
            started = time.monotonic()

            with archive_path.open("wb") as destination:
                for chunk in response.iter_content(chunk_size=self._chunk_size):
                    if not chunk:
                        continue
                    downloaded += len(chunk)
                    if downloaded > self._max_size:
                        raise UpdateDownloadError("Загрузка остановлена: архив слишком большой.")
                    destination.write(chunk)
                    if progress_callback is not None:
                        elapsed = max(time.monotonic() - started, 0.001)
                        progress_callback(downloaded, total, downloaded / elapsed)

            if downloaded <= 0:
                raise UpdateDownloadError("Скачанный архив пуст.")
            if downloaded != plan.asset_size:
                raise UpdateDownloadError(
                    f"Размер скачанного архива ({downloaded}) не совпадает "
                    f"с размером релиза ({plan.asset_size})."
                )

            return UpdateDownloadResult(
                archive_path=archive_path,
                temp_directory=temp_directory,
                bytes_downloaded=downloaded,
                expected_size=plan.asset_size,
            )
        except UpdateDownloadError:
            shutil.rmtree(temp_directory, ignore_errors=True)
            raise
        except (requests.RequestException, OSError) as exc:
            shutil.rmtree(temp_directory, ignore_errors=True)
            raise UpdateDownloadError(f"Не удалось скачать обновление: {exc}") from exc
        except Exception as exc:
            shutil.rmtree(temp_directory, ignore_errors=True)
            raise UpdateDownloadError(f"Не удалось скачать обновление: {exc}") from exc

    def cleanup(self, result: UpdateDownloadResult) -> None:
        """Remove a temporary download after a failed or cancelled workflow."""
        shutil.rmtree(result.temp_directory, ignore_errors=True)

    def _validate_plan(self, plan: UpdatePlan) -> None:
        if not isinstance(plan, UpdatePlan):
            raise UpdateDownloadError("Для загрузки нужен корректный план обновления.")
        if plan.asset_size <= 0:
            raise UpdateDownloadError("Размер архива обновления некорректен.")
        if plan.asset_size > self._max_size:
            raise UpdateDownloadError("Размер архива превышает допустимый лимит.")
        if not plan.download_url.lower().startswith("https://"):
            raise UpdateDownloadError("Скачивание обновления разрешено только по HTTPS.")
        try:
            suggested_archive_path(Path("."), plan)
        except UpdateServiceError as exc:
            raise UpdateDownloadError(str(exc)) from exc

    @staticmethod
    def _content_length(response) -> int | None:
        value = response.headers.get("Content-Length")
        if value is None:
            return None
        try:
            length = int(value)
        except (TypeError, ValueError) as exc:
            raise UpdateDownloadError("Сервер вернул некорректный Content-Length.") from exc
        if length < 0:
            raise UpdateDownloadError("Сервер вернул отрицательный Content-Length.")
        return length
