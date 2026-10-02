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
