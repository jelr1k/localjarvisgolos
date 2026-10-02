from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from services.update_validator import UpdateValidationError, UpdateValidator


def make_zip(path: Path, entries: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return path


def test_validator_accepts_valid_zip(tmp_path):
    archive = make_zip(
        tmp_path / "JARVIS.zip",
        {
            "JARVIS/start.bat": b"start",
            "JARVIS/core/application.py": b"print('ok')",
            "JARVIS/config/settings.json": b"{}",
        },
    )

    result = UpdateValidator().validate(archive, expected_size=archive.stat().st_size)

    assert result.archive_path == archive
    assert result.file_count == 3
    assert result.directory_count == 0
    assert result.total_uncompressed_size == sum(
        len(value)
        for value in (
            b"start",
            b"print('ok')",
            b"{}",
        )
    )


def test_validator_rejects_missing_archive(tmp_path):
    with pytest.raises(UpdateValidationError, match="не найден"):
        UpdateValidator().validate(tmp_path / "missing.zip")


def test_validator_rejects_invalid_zip(tmp_path):
    archive = tmp_path / "broken.zip"
    archive.write_bytes(b"not a zip")

    with pytest.raises(UpdateValidationError, match="ZIP-архив"):
        UpdateValidator().validate(archive)


def test_validator_rejects_size_mismatch(tmp_path):
    archive = make_zip(tmp_path / "JARVIS.zip", {"file.txt": b"hello"})

    with pytest.raises(UpdateValidationError, match="не совпадает"):
        UpdateValidator().validate(archive, expected_size=archive.stat().st_size + 1)


def test_validator_rejects_path_traversal(tmp_path):
    archive = make_zip(tmp_path / "danger.zip", {"../outside.txt": b"bad"})

    with pytest.raises(UpdateValidationError, match="опасный путь"):
        UpdateValidator().validate(archive)


def test_validator_rejects_absolute_path(tmp_path):
    archive = make_zip(tmp_path / "danger.zip", {"/outside.txt": b"bad"})

    with pytest.raises(UpdateValidationError, match="абсолютный путь"):
        UpdateValidator().validate(archive)


def test_validator_rejects_duplicate_entries(tmp_path):
    archive = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("file.txt", b"one")
        zf.writestr("file.txt", b"two")

    with pytest.raises(UpdateValidationError, match="дубликат"):
        UpdateValidator().validate(archive)


def test_validator_rejects_empty_zip(tmp_path):
    archive = tmp_path / "empty.zip"
    with zipfile.ZipFile(archive, "w"):
        pass

    with pytest.raises(UpdateValidationError, match="не содержит"):
        UpdateValidator().validate(archive)
