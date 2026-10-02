from __future__ import annotations

from io import BytesIO
from pathlib import Path
import zipfile

from services.update_backup import UpdateBackupService
from services.update_downloader import UpdateDownloader
from services.update_install_policy import UpdateInstallPolicy
from services.update_installer import UpdateInstallError, UpdateInstaller
from services.update_rollback import UpdateRollbackService
from services.update_service import UpdatePlan
from services.update_validator import UpdateValidator


class FakeResponse:
    def __init__(self, payload: bytes):
        self.headers = {"Content-Length": str(len(payload))}
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        for start in range(0, len(self._payload), chunk_size):
            yield self._payload[start : start + chunk_size]


class FakeSession:
    def __init__(self, payload: bytes):
        self.payload = payload

    def get(self, url: str, *, stream: bool, timeout):
        assert url.startswith("https://")
        assert stream is True
        return FakeResponse(self.payload)


def _make_update_archive() -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("main.py", "print('updated')\n")
        archive.writestr("services/version.py", "APP_VERSION = '0.2.0'\n")
    return buffer.getvalue()


def test_update_pipeline_downloads_validates_backs_up_and_installs(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("print('old')\n", encoding="utf-8")
    (app / "old_module.py").write_text("old\n", encoding="utf-8")

    workspace = app / "workspace"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("keep me\n", encoding="utf-8")

    logs = app / "logs"
    logs.mkdir()
    (logs / "jarvis.log").write_text("keep logs\n", encoding="utf-8")

    payload = _make_update_archive()
    plan = UpdatePlan(
        current_version="0.1.0",
        target_version="0.2.0",
        release_url="https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.2.0",
        asset_name="jarvis.zip",
        download_url="https://github.com/jelr1k/localjarvisgolos/releases/download/v0.2.0/jarvis.zip",
        asset_size=len(payload),
    )

    downloader = UpdateDownloader(
        temp_root=tmp_path / "downloads",
        chunk_size=32,
        session=FakeSession(payload),
    )
    download = downloader.download(plan)

    validation = UpdateValidator().validate(
        download.archive_path,
        expected_size=download.expected_size,
    )
    assert validation.file_count == 2

    backup = UpdateBackupService(tmp_path / "backups").create_backup(app)

    result = UpdateInstaller().install(
        download.archive_path,
        app,
        policy=UpdateInstallPolicy(app),
        expected_size=download.expected_size,
    )

    assert result.installed_files == 2
    assert (app / "main.py").read_text(encoding="utf-8") == "print('updated')\n"
    assert (app / "services/version.py").read_text(encoding="utf-8") == "APP_VERSION = '0.2.0'\n"
    assert not (app / "old_module.py").exists()
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "keep me\n"
    assert (logs / "jarvis.log").read_text(encoding="utf-8") == "keep logs\n"

    downloader.cleanup(download)
    assert not download.temp_directory.exists()
    assert backup.application_backup.is_dir()


def test_update_pipeline_rolls_back_after_install_failure(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "main.py").write_text("print('stable')\n", encoding="utf-8")
    (app / "stable.txt").write_text("stable\n", encoding="utf-8")

    workspace = app / "workspace"
    workspace.mkdir()
    (workspace / "notes.txt").write_text("keep me\n", encoding="utf-8")

    backup = UpdateBackupService(tmp_path / "backups").create_backup(app)

    broken_archive = tmp_path / "broken.zip"
    broken_archive.write_bytes(b"not a zip archive")

    try:
        UpdateInstaller().install(
            broken_archive,
            app,
            policy=UpdateInstallPolicy(app),
            expected_size=broken_archive.stat().st_size,
        )
    except UpdateInstallError:
        pass
    else:
        raise AssertionError("Broken update archive unexpectedly installed")

    # Simulate a failed replacement after the backup has already been created.
    (app / "main.py").write_text("print('broken')\n", encoding="utf-8")
    (app / "stable.txt").unlink()

    rollback = UpdateRollbackService().restore(
        backup.application_backup,
        app,
        policy=UpdateInstallPolicy(app),
    )

    assert rollback.restored_files == 2
    assert (app / "main.py").read_text(encoding="utf-8") == "print('stable')\n"
    assert (app / "stable.txt").read_text(encoding="utf-8") == "stable\n"
    assert (workspace / "notes.txt").read_text(encoding="utf-8") == "keep me\n"
