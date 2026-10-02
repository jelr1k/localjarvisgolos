from __future__ import annotations

from pathlib import Path

import pytest

from services.update_relauncher import UpdateRelaunchError, UpdateRelauncher


def test_relauncher_prepares_plan(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    archive = tmp_path / "update.zip"
    archive.write_bytes(b"zip")
    updater = tmp_path / "updater.py"
    updater.write_text("print('updater')", encoding="utf-8")
    python = tmp_path / "python.exe"
    python.write_bytes(b"python")

    relauncher = UpdateRelauncher(
        updater_path=updater,
        python_executable=python,
    )

    plan = relauncher.prepare(root, archive, 3, process_id=1234)

    assert plan.application_root == root.resolve()
    assert plan.archive_path == archive.resolve()
    assert plan.expected_size == 3
    assert plan.process_id == 1234


def test_relauncher_builds_standalone_command(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    archive = tmp_path / "update.zip"
    archive.write_bytes(b"zip")
    updater = tmp_path / "updater.py"
    updater.write_text("print('updater')", encoding="utf-8")
    python = tmp_path / "python.exe"
    python.write_bytes(b"python")

    relauncher = UpdateRelauncher(
        updater_path=updater,
        python_executable=python,
    )
    plan = relauncher.prepare(root, archive, 3, process_id=1234)

    assert UpdateRelauncher.command(plan) == [
        str(python.resolve()),
        str(updater.resolve()),
        "--pid",
        "1234",
        "--root",
        str(root.resolve()),
        "--archive",
        str(archive.resolve()),
        "--expected-size",
        "3",
    ]


@pytest.mark.parametrize(
    "setup",
    ("missing_root", "missing_archive", "missing_updater", "bad_size", "missing_python"),
)
def test_relauncher_rejects_invalid_setup(tmp_path, setup):
    root = tmp_path / "app"
    archive = tmp_path / "update.zip"
    updater = tmp_path / "updater.py"
    python = tmp_path / "python.exe"

    root.mkdir()
    archive.write_bytes(b"zip")
    updater.write_text("print('updater')", encoding="utf-8")
    python.write_bytes(b"python")

    if setup == "missing_root":
        root.rmdir()
    elif setup == "missing_archive":
        archive.unlink()
    elif setup == "missing_updater":
        updater.unlink()
    elif setup == "missing_python":
        python.unlink()

    kwargs = {
        "updater_path": updater,
        "python_executable": python,
    }
    relauncher = UpdateRelauncher(**kwargs)

    with pytest.raises(UpdateRelaunchError):
        relauncher.prepare(root, archive, 0 if setup == "bad_size" else 3, process_id=1234)
