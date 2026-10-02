"""GitHub Release update checker for JARVIS.

Stage 2 of the updater: only checks release metadata. It does not download,
install, replace files, or restart the application.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

import requests

from core.version import APP_VERSION

DEFAULT_REPOSITORY = "jelr1k/localjarvisgolos"
GITHUB_RELEASES_API = "https://api.github.com/repos/{repository}/releases/latest"
_REQUEST_TIMEOUT = 10.0
_VERSION_RE = re.compile(
    r"^v?(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?P<prerelease>-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$"
)

logger = logging.getLogger("jarvis.update_checker")


class UpdateCheckError(RuntimeError):
    """Raised when GitHub release metadata cannot be checked."""


@dataclass(frozen=True)
class ReleaseAsset:
    """Small release-asset description kept for later updater stages."""

    name: str
    download_url: str
    size: int


@dataclass(frozen=True)
class UpdateInfo:
    """Result of comparing the installed version with a GitHub release."""

    current_version: str
    latest_version: str
    update_available: bool
    release_url: str
    tag_name: str
    release_name: str
    published_at: str | None = None
    prerelease: bool = False
    assets: tuple[ReleaseAsset, ...] = ()


def _parse_version(value: str) -> tuple[int, int, int, tuple[Any, ...]]:
    match = _VERSION_RE.fullmatch(str(value).strip())
    if not match:
        raise ValueError(f"Неверный формат версии: {value!r}")

    core = (
        int(match.group("major")),
        int(match.group("minor")),
        int(match.group("patch")),
    )
    prerelease = match.group("prerelease")
    if not prerelease:
        return (*core, ())

    identifiers: list[Any] = []
    for identifier in prerelease[1:].split("."):
        identifiers.append(int(identifier) if identifier.isdigit() else identifier)
    return (*core, tuple(identifiers))


def _compare_versions(current: str, latest: str) -> int:
    current_core = _parse_version(current)
    latest_core = _parse_version(latest)

    if current_core[:3] != latest_core[:3]:
        return (current_core[:3] > latest_core[:3]) - (current_core[:3] < latest_core[:3])

    current_pre = current_core[3]
    latest_pre = latest_core[3]

    if not current_pre and latest_pre:
        return 1
    if current_pre and not latest_pre:
        return -1
    if current_pre == latest_pre:
        return 0

    for current_id, latest_id in zip(current_pre, latest_pre):
        if current_id == latest_id:
            continue
        if isinstance(current_id, int) and isinstance(latest_id, int):
            return (current_id > latest_id) - (current_id < latest_id)
        if isinstance(current_id, int):
            return -1
        if isinstance(latest_id, int):
            return 1
        return (str(current_id) > str(latest_id)) - (str(current_id) < str(latest_id))

    return (len(current_pre) > len(latest_pre)) - (len(current_pre) < len(latest_pre))


class UpdateChecker:
    """Check the latest published GitHub Release for a JARVIS repository."""

    def __init__(
        self,
        repository: str = DEFAULT_REPOSITORY,
        timeout: float = _REQUEST_TIMEOUT,
        session: requests.Session | None = None,
    ):
        self.repository = repository.strip().strip("/")
        self.timeout = float(timeout)
        self.session = session or requests.Session()
        logger.debug(
            "update_checker_initialized repository=%s timeout=%s api_url=%s",
            self.repository,
            self.timeout,
            self.release_api_url,
        )

    @property
    def release_api_url(self) -> str:
        return GITHUB_RELEASES_API.format(repository=self.repository)

    def check(self, current_version: str = APP_VERSION) -> UpdateInfo:
        """Fetch the latest release and compare it with the installed version."""
        current_version = str(current_version).strip()
        logger.info(
            "update_check_started current_version=%s repository=%s api_url=%s",
            current_version,
            self.repository,
            self.release_api_url,
        )

        try:
            _parse_version(current_version)
        except ValueError as exc:
            logger.error(
                "update_check_invalid_current_version version=%s error=%s",
                current_version,
                exc,
            )
            raise UpdateCheckError(str(exc)) from exc

        try:
            response = self.session.get(
                self.release_api_url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "User-Agent": "JARVIS-Updater",
                },
                timeout=self.timeout,
            )
            logger.info(
                "update_check_http_response status=%s reason=%s",
                getattr(response, "status_code", None),
                getattr(response, "reason", ""),
            )

            if getattr(response, "status_code", None) == 404:
                logger.warning(
                    "update_check_no_release status=404 current_version=%s",
                    current_version,
                )
                return UpdateInfo(
                    current_version=current_version,
                    latest_version=current_version,
                    update_available=False,
                    release_url="",
                    tag_name="",
                    release_name="Релизов пока нет",
                )

            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            logger.exception("update_check_request_failed error=%s", exc)
            raise UpdateCheckError(f"Не удалось проверить обновления: {exc}") from exc
        except ValueError as exc:
            logger.exception("update_check_invalid_github_response error=%s", exc)
            raise UpdateCheckError("GitHub вернул некорректный ответ.") from exc

        if not isinstance(payload, dict):
            logger.error(
                "update_check_unexpected_payload_type type=%s",
                type(payload).__name__,
            )
            raise UpdateCheckError("GitHub вернул неожиданный формат данных.")

        tag_name = str(payload.get("tag_name") or "").strip()
        logger.info(
            "update_check_release_metadata tag=%s name=%s prerelease=%s draft=%s",
            tag_name,
            str(payload.get("name") or ""),
            bool(payload.get("prerelease", False)),
            bool(payload.get("draft", False)),
        )

        try:
            latest_version = _normalize_release_version(tag_name)
        except ValueError as exc:
            logger.error(
                "update_check_invalid_release_version tag=%s error=%s",
                tag_name,
                exc,
            )
            raise UpdateCheckError(
                f"GitHub Release содержит неверную версию: {tag_name!r}"
            ) from exc

        release_url = str(payload.get("html_url") or "").strip()
        if not release_url:
            logger.error("update_check_release_url_missing tag=%s", tag_name)
            raise UpdateCheckError(
                "GitHub Release не содержит ссылки на страницу релиза."
            )

        assets = []
        for item in payload.get("assets") or []:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            download_url = str(item.get("browser_download_url") or "").strip()
            size = item.get("size", 0)
            if name and download_url:
                try:
                    size = int(size)
                except (TypeError, ValueError):
                    size = 0
                assets.append(ReleaseAsset(name, download_url, max(0, size)))

        logger.info(
            "update_check_assets count=%s names=%s",
            len(assets),
            [asset.name for asset in assets],
        )

        update_available = _compare_versions(current_version, latest_version) < 0
        logger.info(
            "update_check_finished current=%s latest=%s update_available=%s tag=%s asset_count=%s",
            current_version,
            latest_version,
            update_available,
            tag_name,
            len(assets),
        )

        return UpdateInfo(
            current_version=current_version,
            latest_version=latest_version,
            update_available=update_available,
            release_url=release_url,
            tag_name=tag_name,
            release_name=str(payload.get("name") or tag_name),
            published_at=payload.get("published_at"),
            prerelease=bool(payload.get("prerelease", False)),
            assets=tuple(assets),
        )


def _normalize_release_version(tag_name: str) -> str:
    value = tag_name.strip()
    if value.lower().startswith("release-"):
        value = value[8:]
    _parse_version(value)
    return value.lstrip("vV")


def check_for_update(
    current_version: str = APP_VERSION,
    repository: str = DEFAULT_REPOSITORY,
    timeout: float = _REQUEST_TIMEOUT,
) -> UpdateInfo:
    """Convenience function for the application and future UI layer."""
    return UpdateChecker(repository=repository, timeout=timeout).check(current_version)
