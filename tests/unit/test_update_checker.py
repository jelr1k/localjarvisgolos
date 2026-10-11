from __future__ import annotations

import requests
import pytest

from services.update_checker import (
    UpdateChecker,
    UpdateCheckError,
    _compare_versions,
    _normalize_release_version,
)


class FakeResponse:
    status_code = 200

    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error

    def raise_for_status(self):
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses) if isinstance(responses, (list, tuple)) else [responses]
        self.calls = []

    def get(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.responses.pop(0)


def test_release_version_normalization():
    assert _normalize_release_version("v0.2.0") == "0.2.0"
    assert _normalize_release_version("release-0.3.1") == "0.3.1"


def test_version_comparison_handles_stable_and_prerelease():
    assert _compare_versions("0.1.0", "0.2.0") < 0
    assert _compare_versions("0.2.0", "0.2.0") == 0
    assert _compare_versions("0.3.0", "0.2.0") > 0
    assert _compare_versions("0.2.0-rc.1", "0.2.0") < 0
    assert _compare_versions("0.2.0-rc.2", "0.2.0-rc.10") < 0


def test_checker_detects_available_update():
    session = FakeSession(
        FakeResponse(
            {
                "tag_name": "v0.2.0",
                "name": "JARVIS 0.2.0",
                "html_url": "https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.2.0",
                "published_at": "2026-10-01T12:00:00Z",
                "prerelease": False,
                "assets": [
                    {
                        "name": "JARVIS.zip",
                        "browser_download_url": "https://github.com/jelr1k/localjarvisgolos/releases/download/v0.2.0/JARVIS.zip",
                        "size": 1234,
                    }
                ],
            }
        )
    )

    info = UpdateChecker(session=session).check("0.1.0")

    assert info.update_available is True
    assert info.latest_version == "0.2.0"
    assert info.tag_name == "v0.2.0"
    assert info.release_name == "JARVIS 0.2.0"
    assert len(info.assets) == 1
    assert info.assets[0].name == "JARVIS.zip"
    assert session.calls[0][0][0].endswith("/releases/latest")
    assert session.calls[0][1]["timeout"] == 10.0


def test_checker_handles_repository_without_releases():
    class NoLatestReleaseResponse(FakeResponse):
        status_code = 404

    session = FakeSession(
        [
            NoLatestReleaseResponse({}),
            FakeResponse([]),
        ]
    )

    info = UpdateChecker(session=session).check("0.1.0")

    assert info.update_available is False
    assert info.latest_version == "0.1.0"
    assert info.release_name == "Релизов пока нет"


def test_checker_reports_no_update_when_versions_match():
    session = FakeSession(
        FakeResponse(
            {
                "tag_name": "0.1.0",
                "name": "JARVIS 0.1.0",
                "html_url": "https://example.com/release",
            }
        )
    )

    info = UpdateChecker(session=session).check("0.1.0")

    assert info.update_available is False


def test_checker_wraps_network_errors():
    session = FakeSession(FakeResponse(error=requests.RequestException("offline")))

    with pytest.raises(UpdateCheckError, match="Не удалось проверить обновления"):
        UpdateChecker(session=session).check("0.1.0")


def test_checker_rejects_invalid_release_version():
    session = FakeSession(
        FakeResponse(
            {
                "tag_name": "latest",
                "html_url": "https://example.com/release",
            }
        )
    )

    with pytest.raises(UpdateCheckError, match="неверную версию"):
        UpdateChecker(session=session).check("0.1.0")


def test_checker_rejects_invalid_current_version():
    session = FakeSession(FakeResponse({}))

    with pytest.raises(UpdateCheckError, match="Неверный формат версии"):
        UpdateChecker(session=session).check("0.1")
