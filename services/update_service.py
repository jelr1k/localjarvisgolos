"""Safe update preparation service for JARVIS.

Stage 6 of the updater: turns a checked GitHub release into an explicit
update plan. It does not download, install, replace files, or restart.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from services.update_checker import ReleaseAsset, UpdateInfo


class UpdateServiceError(RuntimeError):
    """Raised when an update cannot be prepared safely."""


@dataclass(frozen=True)
class UpdatePlan:
    """Validated information needed by a future download/install stage."""

    current_version: str
    target_version: str
    release_url: str
    asset_name: str
    download_url: str
    asset_size: int


class UpdateService:
    """Prepare a validated update without touching the installed application."""

    def __init__(
        self,
        allowed_asset_suffixes: tuple[str, ...] = (".zip",),
    ):
        normalized = tuple(
            suffix.lower() if suffix.startswith(".") else f".{suffix.lower()}"
            for suffix in allowed_asset_suffixes
            if suffix
        )
        if not normalized:
            raise ValueError("Нужно указать хотя бы одно расширение архива.")
        self._allowed_asset_suffixes = normalized

    @property
    def allowed_asset_suffixes(self) -> tuple[str, ...]:
        return self._allowed_asset_suffixes

    def prepare(self, info: UpdateInfo) -> UpdatePlan:
        """Validate a discovered release and return a download/install plan."""
        if not info.update_available:
            raise UpdateServiceError("Нового обновления нет.")

        if not info.latest_version:
            raise UpdateServiceError("Релиз не содержит версии обновления.")

        if not info.release_url or not _is_https_url(info.release_url):
            raise UpdateServiceError("Релиз не содержит безопасной HTTPS-ссылки.")

        asset = self._select_asset(info.assets)
        if asset is None:
            allowed = ", ".join(self._allowed_asset_suffixes)
            raise UpdateServiceError(
                f"В релизе нет подходящего архива ({allowed})."
            )

        if not _is_https_url(asset.download_url):
            raise UpdateServiceError("Ссылка на архив должна использовать HTTPS.")

        if asset.size <= 0:
            raise UpdateServiceError("Размер архива обновления неизвестен или некорректен.")

        return UpdatePlan(
            current_version=info.current_version,
            target_version=info.latest_version,
            release_url=info.release_url,
            asset_name=asset.name,
            download_url=asset.download_url,
            asset_size=asset.size,
        )

    def _select_asset(self, assets: tuple[ReleaseAsset, ...]) -> ReleaseAsset | None:
        candidates = [
            asset
            for asset in assets
            if asset.name.lower().endswith(self._allowed_asset_suffixes)
        ]
        if not candidates:
            return None

        if len(candidates) == 1:
            return candidates[0]

        preferred_names = ("jarvis.zip", "jarvis-update.zip", "update.zip")
        for preferred in preferred_names:
            for asset in candidates:
                if asset.name.lower() == preferred:
                    return asset

        raise UpdateServiceError(
            "В релизе найдено несколько подходящих архивов обновления."
        )


def _is_https_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return parsed.scheme.lower() == "https" and bool(parsed.netloc)


def suggested_archive_path(directory: Path, plan: UpdatePlan) -> Path:
    """Return a safe local filename for a future download stage."""
    name = Path(plan.asset_name).name
    if name in {"", ".", ".."}:
        raise UpdateServiceError("Имя архива обновления некорректно.")
    if not name.lower().endswith((".zip",)):
        raise UpdateServiceError("Подготовленный архив должен иметь расширение .zip.")
    return directory / name
