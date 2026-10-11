from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

import pytest

from services.update_backup import UpdateBackupService
from services.update_checker import UpdateChecker
from services.update_downloader import UpdateDownloader
from services.update_install_policy import UpdateInstallPolicy
from services.update_installer import UpdateInstallError, UpdateInstaller
from services.update_rollback import UpdateRollbackService
from services.update_service import UpdateService
from services.update_validator import UpdateValidator


class FakeResponse:
    status_code = 200

    def __init__(self, payload=None, *, body: bytes | None = None):
        self.payload = payload
        self._body = body or b""
        self.headers = {"Content-Length": str(len(self._body))} if body is not None else {}
        self.error = None

    def raise_for_status(self) -> None:
        if self.error is not None:
            raise self.error

    def json(self):
        return self.payload

    def iter_content(self, chunk_size: int):
        for start in range(0, len(self._body), chunk_size):
            yield self._body[start : start + chunk_size]


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        return response


def _make_update_archive() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("JARVIS/main.py", "print('updated')\n")
        archive.writestr("JARVIS/services/new_module.py", "NEW = True\n")
        archive.writestr("JARVIS/workspace/note.txt", "archive copy must not overwrite user data\n")
        archive.writestr("JARVIS/logs/jarvis.log", "archive copy must not overwrite logs\n")
    return buffer.getvalue()


def _make_release_payload(archive_size: int) -> dict:
    return {
        "tag_name": "v0.2.0",
        "name": "JARVIS 0.2.0",
        "html_url": "https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.2.0",
        "published_at": "2026-10-08T12:00:00Z",
        "prerelease": False,
        "assets": [
            {
                "name": "JARVIS.zip",
                "browser_download_url": (
                    "https://github.com/jelr1k/localjarvisgolos/releases/"
                    "download/v0.2.0/JARVIS.zip"
                ),
                "size": archive_size,
            }
        ],
    }


def _make_policy(app: Path, tmp_path: Path) -> UpdateInstallPolicy:
    return UpdateInstallPolicy(
        app,
        app_data_dir=tmp_path / "AppData" / "Jarvis",
        environment={
            "HF_HUB_CACHE": str(tmp_path / "hf-cache"),
            "OLLAMA_MODELS": str(tmp_path / "ollama-models"),
        },
        home_dir=tmp_path / "home",
    )


def test_synthetic_update_pipeline_uses_fake_github_and_real_filesystem(tmp_path):
    """Exercise checker -> planner -> downloader -> validator -> backup -> installer."""
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("print('stable')\n", encoding="utf-8")
    (app / "old_module.py").write_text("old\n", encoding="utf-8")

    workspace = app / "workspace"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("user data\n", encoding="utf-8")

    logs = app / "logs"
    logs.mkdir()
    (logs / "jarvis.log").write_text("existing logs\n", encoding="utf-8")

    app_data = tmp_path / "AppData" / "Jarvis"
    app_data.mkdir(parents=True)
    (app_data / "settings.json").write_text("{\"model\":\"qwen3:1.7b\"}", encoding="utf-8")

    archive_payload = _make_update_archive()
    session = FakeSession(
        [
            FakeResponse(_make_release_payload(len(archive_payload))),
            FakeResponse(body=archive_payload),
        ]
    )

    checker = UpdateChecker(session=session)
    info = checker.check("0.1.0")
    assert info.update_available is True
    assert info.latest_version == "0.2.0"
    assert info.assets[0].size == len(archive_payload)

    plan = UpdateService().prepare(info)
    assert plan.asset_name == "JARVIS.zip"

    downloads = tmp_path / "downloads"
    downloads.mkdir()
    download = UpdateDownloader(
        temp_root=downloads,
        chunk_size=17,
        session=session,
    ).download(plan)

    validation = UpdateValidator().validate(
        download.archive_path,
        expected_size=download.expected_size,
    )
    assert validation.file_count == 4

    policy = _make_policy(app, tmp_path)
    backup = UpdateBackupService(tmp_path / "backups").create_backup(
        app,
        preserve_paths=(app_data,),
    )

    result = UpdateInstaller().install(
        download.archive_path,
        app,
        policy=policy,
        expected_size=download.expected_size,
    )

    assert result.installed_files == 2
    assert (app / "main.py").read_text(encoding="utf-8") == "print('updated')\n"
    assert (app / "services" / "new_module.py").read_text(encoding="utf-8") == "NEW = True\n"
    assert not (app / "old_module.py").exists()
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "user data\n"
    assert (logs / "jarvis.log").read_text(encoding="utf-8") == "existing logs\n"
    assert (app_data / "settings.json").read_text(encoding="utf-8") == "{\"model\":\"qwen3:1.7b\"}"

    assert backup.application_backup.is_dir()
    assert len(session.calls) == 2
    assert session.calls[0][0].endswith("/releases/latest")
    assert session.calls[1][0] == plan.download_url

    UpdateDownloader(session=session, temp_root=downloads).cleanup(download)


def test_synthetic_pipeline_rolls_back_partial_install_without_touching_user_data(
    tmp_path,
    monkeypatch,
):
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("stable\n", encoding="utf-8")
    (app / "stable.txt").write_text("keep\n", encoding="utf-8")

    workspace = app / "workspace"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("user\n", encoding="utf-8")

    policy = _make_policy(app, tmp_path)
    backup = UpdateBackupService(tmp_path / "backups").create_backup(app)

    archive = tmp_path / "partial.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("JARVIS/main.py", "new\n")
        zf.writestr("JARVIS/z_new.py", "new file\n")

    def fail_after_partial_replace(self, source_root, destination_root, install_policy):
        (destination_root / "main.py").write_text("broken\n", encoding="utf-8")
        (destination_root / "z_new.py").write_text("partial\n", encoding="utf-8")
        raise UpdateInstallError("synthetic install failure")

    monkeypatch.setattr(UpdateInstaller, "_replace_application_files", fail_after_partial_replace)

    with pytest.raises(UpdateInstallError, match="synthetic install failure"):
        UpdateInstaller().install(
            archive,
            app,
            policy=policy,
            expected_size=archive.stat().st_size,
        )

    rollback = UpdateRollbackService().restore(
        backup.application_backup,
        app,
        policy=policy,
    )

    assert rollback.restored_files == 2
    assert (app / "main.py").read_text(encoding="utf-8") == "stable\n"
    assert (app / "stable.txt").read_text(encoding="utf-8") == "keep\n"
    assert not (app / "z_new.py").exists()
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "user\n"

