from __future__ import annotations

from pathlib import Path

import pytest

from services.update_rollback import UpdateRollbackError, UpdateRollbackService


def test_rollback_restores_previous_application_and_preserves_user_data(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    (root / "main.py").write_text("broken", encoding="utf-8")
    (root / "new.py").write_text("new", encoding="utf-8")

    (root / "workspace").mkdir()
    (root / "workspace" / "note.txt").write_text("user", encoding="utf-8")
    (root / "logs").mkdir()
    (root / "logs" / "jarvis.log").write_text("log", encoding="utf-8")

    backup = tmp_path / "backup"
    backup.mkdir()
    (backup / "main.py").write_text("working", encoding="utf-8")
    (backup / "old.py").write_text("old", encoding="utf-8")

    result = UpdateRollbackService().restore(backup, root)

    assert result.restored_files == 2
    assert (root / "main.py").read_text(encoding="utf-8") == "working"
    assert (root / "old.py").read_text(encoding="utf-8") == "old"
    assert not (root / "new.py").exists()
    assert (root / "workspace" / "note.txt").read_text(encoding="utf-8") == "user"
    assert (root / "logs" / "jarvis.log").read_text(encoding="utf-8") == "log"


def test_rollback_requires_existing_backup(tmp_path):
    root = tmp_path / "app"
    root.mkdir()

    with pytest.raises(UpdateRollbackError, match="не найдена"):
        UpdateRollbackService().restore(tmp_path / "missing", root)


def test_rollback_requires_existing_application(tmp_path):
    backup = tmp_path / "backup"
    backup.mkdir()

    with pytest.raises(UpdateRollbackError, match="не найден"):
        UpdateRollbackService().restore(backup, tmp_path / "missing")
