from __future__ import annotations

from pathlib import Path

import pytest

from services.update_backup import UpdateBackupError, UpdateBackupService


def test_backup_copies_application_and_preserved_paths(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("old", encoding="utf-8")
    (app / "config").mkdir()
    (app / "config" / "settings.json").write_text("{}", encoding="utf-8")

    user_data = tmp_path / "user-data"
    user_data.mkdir()
    (user_data / "settings.json").write_text("user", encoding="utf-8")

    backups = tmp_path / "backups"
    result = UpdateBackupService(backups).create_backup(
        app,
        preserve_paths=(user_data,),
    )

    assert (result.application_backup / "main.py").read_text(encoding="utf-8") == "old"
    assert (result.application_backup / "config" / "settings.json").exists()
    assert result.preserved_paths == (user_data.resolve(),)
    preserved_files = list((result.backup_directory / "preserved").rglob("settings.json"))
    assert preserved_files
    assert preserved_files[0].read_text(encoding="utf-8") == "user"


def test_backup_does_not_copy_symlinks(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    target = tmp_path / "outside.txt"
    target.write_text("outside", encoding="utf-8")
    link = app / "link.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this Windows configuration.")

    result = UpdateBackupService(tmp_path / "backups").create_backup(app)
    assert not (result.application_backup / "link.txt").exists()


def test_backup_missing_application_fails(tmp_path):
    with pytest.raises(UpdateBackupError, match="не найден"):
        UpdateBackupService(tmp_path / "backups").create_backup(tmp_path / "missing")


def test_backup_cleans_partial_result_on_copy_failure(tmp_path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("old", encoding="utf-8")

    service = UpdateBackupService(tmp_path / "backups")

    def fail_copy2(*args, **kwargs):
        raise OSError("disk error")

    monkeypatch.setattr("services.update_backup.shutil.copy2", fail_copy2)

    with pytest.raises(UpdateBackupError, match="disk error"):
        service.create_backup(app)

    assert not list((tmp_path / "backups").glob("jarvis-backup-*"))


def test_backup_removes_previous_backup_after_new_one_succeeds(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("version-1", encoding="utf-8")

    backups = tmp_path / "backups"
    service = UpdateBackupService(backups)

    first = service.create_backup(app)
    assert first.backup_directory.exists()

    (app / "main.py").write_text("version-2", encoding="utf-8")
    second = service.create_backup(app)

    assert second.backup_directory.exists()
    assert not first.backup_directory.exists()
    assert list(backups.glob("jarvis-backup-*")) == [second.backup_directory]
    assert (second.application_backup / "main.py").read_text(encoding="utf-8") == "version-2"


def test_backup_keeps_previous_backup_if_new_backup_fails(tmp_path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("version-1", encoding="utf-8")

    backups = tmp_path / "backups"
    service = UpdateBackupService(backups)
    first = service.create_backup(app)

    def fail_copy2(*args, **kwargs):
        raise OSError("disk error")

    monkeypatch.setattr("services.update_backup.shutil.copy2", fail_copy2)

    with pytest.raises(UpdateBackupError, match="disk error"):
        service.create_backup(app)

    assert first.backup_directory.exists()
    assert list(backups.glob("jarvis-backup-*")) == [first.backup_directory]



def test_backup_excludes_development_and_runtime_directories_and_records_inventory(tmp_path):
    import json

    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("source", encoding="utf-8")
    for directory, filename in (
        (".git", "config"),
        (".venv", "pyvenv.cfg"),
        ("tests", "test_sample.py"),
        ("workspace", "notes.txt"),
        ("logs", "jarvis.log"),
        ("models", "weights.bin"),
    ):
        folder = app / directory
        folder.mkdir()
        (folder / filename).write_text("do not copy", encoding="utf-8")

    result = UpdateBackupService(tmp_path / "backups").create_backup(app)

    assert (result.application_backup / "main.py").read_text(encoding="utf-8") == "source"
    for directory in (".git", ".venv", "tests", "workspace", "logs", "models"):
        assert not (result.application_backup / directory).exists()

    inventory = json.loads(
        (result.backup_directory / "application-inventory.json").read_text(encoding="utf-8")
    )
    assert inventory["schema_version"] == 1
    assert inventory["files"] == ["main.py"]
