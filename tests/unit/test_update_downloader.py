from __future__ import annotations

from pathlib import Path

import pytest

from services.update_checker import ReleaseAsset, UpdateInfo
from services.update_downloader import UpdateDownloadError, UpdateDownloader
from services.update_service import UpdateService


class FakeResponse:
    def __init__(self, chunks, content_length=None):
        self._chunks = chunks
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield from self._chunks


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response


def make_plan(size=6):
    info = UpdateInfo(
        current_version="0.1.0",
        latest_version="0.2.0",
        update_available=True,
        release_url="https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.2.0",
        tag_name="v0.2.0",
        release_name="JARVIS 0.2.0",
        assets=(ReleaseAsset("JARVIS.zip", "https://example.com/JARVIS.zip", size),),
    )
    return UpdateService().prepare(info)


def test_download_streams_archive_to_isolated_temp_directory(tmp_path):
    session = FakeSession(FakeResponse([b"abc", b"def"], content_length=6))
    downloader = UpdateDownloader(temp_root=tmp_path, session=session, chunk_size=3)

    progress = []
    result = downloader.download(make_plan(), lambda current, total, speed: progress.append((current, total)))

    assert result.archive_path.exists()
    assert result.archive_path.read_bytes() == b"abcdef"
    assert result.archive_path.parent.parent == tmp_path
    assert result.bytes_downloaded == 6
    assert progress[-1] == (6, 6)
    assert session.calls[0][0] == "https://example.com/JARVIS.zip"
    assert session.calls[0][1]["stream"] is True

    downloader.cleanup(result)
    assert not result.temp_directory.exists()


def test_download_rejects_server_size_mismatch(tmp_path):
    session = FakeSession(FakeResponse([b"abc"], content_length=3))
    downloader = UpdateDownloader(temp_root=tmp_path, session=session)

    with pytest.raises(UpdateDownloadError, match="не совпадает"):
        downloader.download(make_plan(size=6))

    assert list(tmp_path.iterdir()) == []


def test_download_rejects_downloaded_size_mismatch(tmp_path):
    session = FakeSession(FakeResponse([b"abc"], content_length=None))
    downloader = UpdateDownloader(temp_root=tmp_path, session=session)

    with pytest.raises(UpdateDownloadError, match="не совпадает"):
        downloader.download(make_plan(size=6))

    assert list(tmp_path.iterdir()) == []


def test_download_rejects_oversized_content(tmp_path):
    session = FakeSession(FakeResponse([b"abcdefg"], content_length=7))
    downloader = UpdateDownloader(temp_root=tmp_path, session=session, max_size=6)

    with pytest.raises(UpdateDownloadError, match="превышает"):
        downloader.download(make_plan(size=6))

    assert list(tmp_path.iterdir()) == []


def test_download_rejects_non_update_plan(tmp_path):
    downloader = UpdateDownloader(temp_root=tmp_path)

    with pytest.raises(UpdateDownloadError, match="корректный план"):
        downloader.download(None)


def test_download_cleans_temp_directory_on_write_error(tmp_path, monkeypatch):
    session = FakeSession(FakeResponse([b"abc"], content_length=3))
    downloader = UpdateDownloader(temp_root=tmp_path, session=session)

    original_open = Path.open

    def fail_open(self, *args, **kwargs):
        if self.name == "JARVIS.zip":
            raise OSError("disk error")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fail_open)

    with pytest.raises(UpdateDownloadError, match="Не удалось скачать"):
        downloader.download(make_plan(size=3))

    assert list(tmp_path.iterdir()) == []
