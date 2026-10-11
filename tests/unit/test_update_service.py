from __future__ import annotations

from pathlib import Path

import pytest

from services.update_checker import ReleaseAsset, UpdateInfo
from services.update_service import (
    UpdateService,
    UpdateServiceError,
    suggested_archive_path,
)


def make_info(
    *,
    available=True,
    assets=(
        ReleaseAsset(
            name="JARVIS.zip",
            download_url="https://github.com/jelr1k/localjarvisgolos/releases/download/v0.2.0/JARVIS.zip",
            size=1024,
        ),
    ),
):
    return UpdateInfo(
        current_version="0.1.0",
        latest_version="0.2.0",
        update_available=available,
        release_url="https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.2.0",
        tag_name="v0.2.0",
        release_name="JARVIS 0.2.0",
        assets=assets,
    )


def test_prepare_builds_valid_update_plan():
    plan = UpdateService().prepare(make_info())

    assert plan.current_version == "0.1.0"
    assert plan.target_version == "0.2.0"
    assert plan.asset_name == "JARVIS.zip"
    assert plan.asset_size == 1024
    assert plan.download_url.startswith("https://")


def test_prepare_rejects_when_no_update_is_available():
    with pytest.raises(UpdateServiceError, match="Нового обновления нет"):
        UpdateService().prepare(make_info(available=False))


def test_prepare_rejects_missing_archive():
    info = make_info(assets=())

    with pytest.raises(UpdateServiceError, match="нет подходящего архива"):
        UpdateService().prepare(info)


def test_prepare_rejects_non_https_archive():
    info = make_info(
        assets=(
            ReleaseAsset("JARVIS.zip", "http://example.com/JARVIS.zip", 1024),
        )
    )

    with pytest.raises(UpdateServiceError, match="HTTPS"):
        UpdateService().prepare(info)


def test_prepare_rejects_unknown_archive_size():
    info = make_info(
        assets=(
            ReleaseAsset(
                "JARVIS.zip",
                "https://example.com/JARVIS.zip",
                0,
            ),
        )
    )

    with pytest.raises(UpdateServiceError, match="Размер архива"):
        UpdateService().prepare(info)


def test_prepare_prefers_jarvis_archive_when_multiple_zip_assets_exist():
    info = make_info(
        assets=(
            ReleaseAsset("symbols.zip", "https://example.com/symbols.zip", 100),
            ReleaseAsset("JARVIS.zip", "https://example.com/JARVIS.zip", 200),
        )
    )

    plan = UpdateService().prepare(info)

    assert plan.asset_name == "JARVIS.zip"
    assert plan.asset_size == 200


def test_prepare_rejects_ambiguous_zip_assets():
    info = make_info(
        assets=(
            ReleaseAsset("one.zip", "https://example.com/one.zip", 100),
            ReleaseAsset("two.zip", "https://example.com/two.zip", 200),
        )
    )

    with pytest.raises(UpdateServiceError, match="несколько подходящих"):
        UpdateService().prepare(info)


def test_suggested_archive_path_uses_only_asset_filename():
    info = make_info()
    plan = UpdateService().prepare(info)

    path = suggested_archive_path(Path("temp"), plan)

    assert path == Path("temp") / "JARVIS.zip"
    assert path.parent == Path("temp")


def test_prepare_rejects_insecure_release_page():
    info = make_info()
    info = UpdateInfo(
        **{**info.__dict__, "release_url": "http://github.com/release"}
    )

    with pytest.raises(UpdateServiceError, match="HTTPS"):
        UpdateService().prepare(info)
