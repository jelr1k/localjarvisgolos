from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from services.update_install_policy import UpdateInstallPolicy
from services.update_install_policy import ProtectedPath
from services.update_install_policy import UpdateInstallPolicy
from services.update_installer import UpdateInstallError, UpdateInstaller


def make_archive(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def make_policy(app: Path, tmp_path: Path) -> UpdateInstallPolicy:
    return UpdateInstallPolicy(
        app,
        app_data_dir=tmp_path / "AppData" / "Jarvis",
        environment={
            "HF_HUB_CACHE": str(tmp_path / "hf-cache"),
            "OLLAMA_MODELS": str(tmp_path / "ollama-models"),
        },
        home_dir=tmp_path / "home",
    )


def test_installer_replaces_application_files_and_removes_old_owned_files(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "old.py").write_text("old", encoding="utf-8")
    (app / "services").mkdir()
    (app / "services" / "old.py").write_text("old", encoding="utf-8")

    archive = make_archive(
        tmp_path / "JARVIS.zip",
        {
            "JARVIS/main.py": b"new",
            "JARVIS/services/new.py": b"new-service",
        },
    )

    result = UpdateInstaller().install(
        archive,
        app,
        policy=make_policy(app, tmp_path),
        expected_size=archive.stat().st_size,
    )

    assert (app / "main.py").read_text(encoding="utf-8") == "new"
    assert (app / "services" / "new.py").read_text(encoding="utf-8") == "new-service"
    assert not (app / "old.py").exists()
    assert not (app / "services" / "old.py").exists()
    assert result.installed_files == 2


def test_installer_preserves_workspace_logs_and_models(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    for name, value in (
        ("workspace/note.txt", "note"),
        ("logs/jarvis.log", "log"),
        ("models/model.bin", "model"),
    ):
        path = app / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    archive = make_archive(
        tmp_path / "JARVIS.zip",
        {
            "JARVIS/main.py": b"new",
            "JARVIS/workspace/note.txt": b"replace",
            "JARVIS/logs/jarvis.log": b"replace",
            "JARVIS/models/model.bin": b"replace",
        },
    )

    UpdateInstaller().install(
        archive,
        app,
        policy=make_policy(app, tmp_path),
        expected_size=archive.stat().st_size,
    )

    assert (app / "workspace/note.txt").read_text(encoding="utf-8") == "note"
    assert (app / "logs/jarvis.log").read_text(encoding="utf-8") == "log"
    assert (app / "models/model.bin").read_text(encoding="utf-8") == "model"


def test_installer_rejects_invalid_archive(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    archive = tmp_path / "bad.zip"
    archive.write_bytes(b"not zip")

    with pytest.raises(UpdateInstallError, match="не прошёл повторную проверку"):
        UpdateInstaller().install(archive, app, policy=make_policy(app, tmp_path))


def test_installer_rejects_path_traversal(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    archive = make_archive(tmp_path / "danger.zip", {"../outside.txt": b"bad"})

    with pytest.raises(UpdateInstallError, match="не прошёл повторную проверку"):
        UpdateInstaller().install(archive, app, policy=make_policy(app, tmp_path))


def test_installer_requires_existing_application_root(tmp_path):
    archive = make_archive(tmp_path / "JARVIS.zip", {"JARVIS/main.py": b"new"})

    with pytest.raises(UpdateInstallError, match="не найден"):
        UpdateInstaller().install(
            archive,
            tmp_path / "missing",
            policy=None,
        )


def test_installer_preserves_external_user_data(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    user_data = tmp_path / "AppData" / "Jarvis"
    user_data.mkdir(parents=True)
    (user_data / "settings.json").write_text("user", encoding="utf-8")

    archive = make_archive(
        tmp_path / "JARVIS.zip",
        {"JARVIS/main.py": b"new"},
    )

    policy = UpdateInstallPolicy(
        app,
        app_data_dir=user_data,
        environment={
            "HF_HUB_CACHE": str(tmp_path / "hf"),
            "OLLAMA_MODELS": str(tmp_path / "ollama"),
        },
        home_dir=tmp_path / "home",
    )

    UpdateInstaller().install(
        archive,
        app,
        policy=policy,
        expected_size=archive.stat().st_size,
    )

    assert (user_data / "settings.json").read_text(encoding="utf-8") == "user"
