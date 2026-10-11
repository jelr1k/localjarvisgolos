from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.update_health import UPDATE_HEALTH_ENV, write_startup_health_marker
from start.updater import _cleanup_archive, _wait_for_startup


class FakeProcess:
    def __init__(self, return_code=None):
        self.return_code = return_code

    def poll(self):
        return self.return_code


def test_startup_health_marker_is_optional_for_normal_launch(tmp_path, monkeypatch):
    monkeypatch.delenv(UPDATE_HEALTH_ENV, raising=False)

    assert write_startup_health_marker("0.1.0") is False


def test_startup_health_marker_is_written_atomically_for_updater(tmp_path, monkeypatch):
    marker = tmp_path / "temp" / "startup-health.json"
    monkeypatch.setenv(UPDATE_HEALTH_ENV, str(marker))

    assert write_startup_health_marker("0.2.0") is True
    assert json.loads(marker.read_text(encoding="utf-8")) == {
        "status": "ready",
        "version": "0.2.0",
    }
    assert not list(marker.parent.glob("*.tmp"))


def test_updater_waits_for_explicit_startup_success(tmp_path):
    marker = tmp_path / "startup-health.json"
    marker.write_text(
        json.dumps({"status": "ready", "version": "0.2.0"}),
        encoding="utf-8",
    )

    result = _wait_for_startup(FakeProcess(), marker, timeout=0.1, poll_interval=0.01)

    assert result["status"] == "ready"
    assert result["version"] == "0.2.0"


def test_updater_rejects_child_that_exits_before_startup_success(tmp_path):
    with pytest.raises(RuntimeError, match="завершился до подтверждения"):
        _wait_for_startup(
            FakeProcess(return_code=1),
            tmp_path / "missing-health.json",
            timeout=0.2,
            poll_interval=0.01,
        )


def test_updater_times_out_without_a_health_marker(tmp_path):
    with pytest.raises(TimeoutError, match="не подтвердил успешный запуск"):
        _wait_for_startup(
            FakeProcess(),
            tmp_path / "missing-health.json",
            timeout=0.1,
            poll_interval=0.01,
        )


def test_archive_cleanup_removes_only_its_dedicated_temp_directory(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    safe_dir = tmp_path / "jarvis-update-test"
    safe_dir.mkdir()
    safe_archive = safe_dir / "update.zip"
    safe_archive.write_bytes(b"archive")

    _cleanup_archive(safe_archive, app)
    assert not safe_dir.exists()

    unsafe_dir = app / "jarvis-update-do-not-delete"
    unsafe_dir.mkdir()
    unsafe_archive = unsafe_dir / "update.zip"
    unsafe_archive.write_bytes(b"archive")

    _cleanup_archive(unsafe_archive, app)
    assert unsafe_archive.exists()
