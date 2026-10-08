from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import core.app_paths as app_paths
import start.bootstrap as bootstrap
import start.updater as updater


def test_app_paths_runtime_root_is_project_root_when_not_frozen(tmp_path):
    with patch.object(app_paths.sys, "frozen", False, create=True):
        root = app_paths.get_application_root()

    assert root == Path(app_paths.__file__).resolve().parents[1]


def test_app_paths_supports_frozen_and_meipass_layout(tmp_path):
    executable = tmp_path / "Jarvis.exe"
    meipass = tmp_path / "bundle"
    meipass.mkdir()

    with patch.object(app_paths.sys, "frozen", True, create=True),          patch.object(app_paths.sys, "executable", str(executable), create=True):
        assert app_paths.get_application_root() == tmp_path

    with patch.object(app_paths.sys, "_MEIPASS", str(meipass), create=True):
        assert app_paths.get_resource_root() == meipass.resolve()


def test_ensure_application_dirs_creates_runtime_directories(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    logs = tmp_path / "logs"
    data = tmp_path / "data"

    monkeypatch.setattr(app_paths, "WORKSPACE_DIR", workspace)
    monkeypatch.setattr(app_paths, "LOG_DIR", logs)
    monkeypatch.setattr(app_paths, "APP_DATA_DIR", data)

    app_paths.ensure_application_dirs()

    assert workspace.is_dir()
    assert logs.is_dir()
    assert data.is_dir()


def test_bundled_config_path_uses_resource_root(tmp_path, monkeypatch):
    monkeypatch.setattr(app_paths, "RESOURCE_ROOT", tmp_path)
    assert app_paths.bundled_config_path() == tmp_path / "config" / "settings.json"


def test_bootstrap_project_root_does_not_depend_on_current_working_directory():
    with patch.object(bootstrap, "APP_DIR", Path(bootstrap.__file__).resolve().parent):
        root = bootstrap._find_project_root()
    assert (root / "core").is_dir()


def test_bootstrap_clears_stale_logs(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "old.log").write_text("x", encoding="utf-8")
    (log_dir / "keep.txt").write_text("keep", encoding="utf-8")

    with patch.object(bootstrap, "LOG_DIR", log_dir):
        bootstrap._clear_previous_logs()

    assert not (log_dir / "old.log").exists()
    assert (log_dir / "keep.txt").exists()


def test_bootstrap_main_runs_main_py_and_returns_system_exit_code(tmp_path):
    logger = Mock()

    with patch.object(bootstrap, "_clear_previous_logs"),          patch.object(bootstrap, "_setup_bootstrap_logging", return_value=logger),          patch.object(bootstrap, "_install_exception_hooks"),          patch.object(bootstrap, "_enable_fatal_error_logging"),          patch.object(bootstrap.runpy, "run_path", side_effect=SystemExit(3)):
        assert bootstrap.main() == 3


def test_bootstrap_main_returns_one_on_unhandled_startup_error():
    logger = Mock()

    with patch.object(bootstrap, "_clear_previous_logs"),          patch.object(bootstrap, "_setup_bootstrap_logging", return_value=logger),          patch.object(bootstrap, "_install_exception_hooks"),          patch.object(bootstrap, "_enable_fatal_error_logging"),          patch.object(bootstrap.runpy, "run_path", side_effect=RuntimeError("boom")):
        assert bootstrap.main() == 1


def test_updater_argument_parser(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "updater.py",
            "--pid", "123",
            "--root", "C:/Jarvis",
            "--archive", "C:/tmp/update.zip",
            "--backup", "C:/tmp/backup",
            "--expected-size", "42",
        ],
    )

    args = updater._parse_args()

    assert args.pid == 123
    assert args.root == Path("C:/Jarvis")
    assert args.archive == Path("C:/tmp/update.zip")
    assert args.backup == Path("C:/tmp/backup")
    assert args.expected_size == 42


def test_updater_process_check_uses_tasklist():
    with patch("start.updater.subprocess.run", return_value=Mock(stdout="jarvis.exe 123 Console")) as run:
        assert updater._is_process_running(123) is True
        run.assert_called_once()

    with patch("start.updater.subprocess.run", return_value=Mock(stdout="INFO: no tasks")):
        assert updater._is_process_running(123) is False

    assert updater._is_process_running(0) is False


def test_updater_waits_until_process_exits_without_real_sleep():
    running = iter([True, False])

    with patch("start.updater._is_process_running", side_effect=lambda pid: next(running)),          patch("start.updater.time.sleep"):
        updater._wait_for_process_exit(123, timeout=10)


def test_updater_wait_times_out():
    with patch("start.updater._is_process_running", return_value=True),          patch("start.updater.time.monotonic", side_effect=[0.0, 11.0]),          patch("start.updater.time.sleep"):
        with pytest.raises(TimeoutError):
            updater._wait_for_process_exit(123, timeout=10)


def test_updater_restart_requires_bootstrap(tmp_path):
    with pytest.raises(FileNotFoundError):
        updater._restart(tmp_path)


def test_updater_cleanup_removes_temporary_archive_directory(tmp_path):
    archive = tmp_path / "download" / "JARVIS.zip"
    archive.parent.mkdir()
    archive.write_text("x", encoding="utf-8")

    updater._cleanup_archive(archive)

    assert not archive.parent.exists()
