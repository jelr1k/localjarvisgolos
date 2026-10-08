from __future__ import annotations

from pathlib import Path

import pytest

from security import sandbox
from tools import files, paths


@pytest.fixture
def workspace(monkeypatch, tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(paths, "TOOL_WORKSPACE", root)
    monkeypatch.setattr(paths, "APP_ROOT", root)
    monkeypatch.setattr(sandbox, "WORKSPACE_DIR", root)
    return root


def test_create_read_and_write_file(workspace):
    created = files.create_file("notes/test.txt", "hello")
    assert created["success"] is True
    assert (workspace / "notes" / "test.txt").read_text(encoding="utf-8") == "hello"

    written = files.write_file("notes/test.txt", "changed")
    assert written["success"] is True

    read = files.read_file("notes/test.txt")
    assert read["success"] is True
    assert read["content"] == "changed"
    assert read["details"]["size"] == len("changed".encode("utf-8"))


def test_create_existing_file_is_rejected(workspace):
    (workspace / "test.txt").write_text("old", encoding="utf-8")
    result = files.create_file("test.txt", "new")
    assert result["success"] is False
    assert "уже существует" in result["error"]


def test_create_folder_and_file_info(workspace):
    folder = files.create_folder("docs")
    assert folder["success"] is True, folder

    (workspace / "docs" / "readme.md").write_text("abc", encoding="utf-8")
    info = files.file_info("readme.md")
    assert info["success"] is True, info
    assert info["details"]["name"] == "readme.md"
    assert info["details"]["extension"] == ".md"
    assert info["details"]["size"] == 3


def test_rename_copy_and_move_file(workspace):
    (workspace / "a.txt").write_text("abc", encoding="utf-8")

    renamed = files.rename_file("a.txt", "b.txt")
    assert renamed["success"] is True
    assert not (workspace / "a.txt").exists()
    assert (workspace / "b.txt").exists()

    copied = files.copy_file("b.txt", "copies/c.txt")
    assert copied["success"] is True
    assert (workspace / "copies" / "c.txt").read_text(encoding="utf-8") == "abc"

    moved = files.move_file("copies/c.txt", "moved/c.txt")
    assert moved["success"] is True
    assert not (workspace / "copies" / "c.txt").exists()
    assert (workspace / "moved" / "c.txt").exists()


def test_rename_rejects_nested_destination_name(workspace):
    (workspace / "a.txt").write_text("abc", encoding="utf-8")
    result = files.rename_file("a.txt", "nested/b.txt")
    assert result["success"] is False
    assert "именем файла" in result["error"]


def test_read_rejects_non_utf8_and_oversized_file(workspace):
    binary = workspace / "binary.txt"
    binary.write_bytes(b"\xff\xfe")

    result = files.read_file("binary.txt")
    assert result["success"] is False
    assert "UTF-8" in result["error"]

    huge = workspace / "huge.txt"
    huge.write_bytes(b"x" * (files.MAX_READ_BYTES + 1))
    result = files.read_file("huge.txt")
    assert result["success"] is False
    assert "слишком большой" in result["error"]


def test_search_files_filters_extension_and_supports_fuzzy_name(workspace):
    (workspace / "report.json").write_text("{}", encoding="utf-8")
    (workspace / "report.txt").write_text("txt", encoding="utf-8")

    exact = files.search_files("report.json", "json")
    assert exact["success"] is True
    assert [Path(item).name for item in exact["matches"]] == ["report.json"]

    fuzzy = files.search_files("reprot.json")
    assert fuzzy["success"] is True
    assert fuzzy["matches"]


def test_file_tools_reject_empty_or_outside_paths(workspace):
    assert files.create_file("")[ "success"] is False

    outside = workspace.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    result = files.read_file(str(outside))
    assert result["success"] is False
    assert outside.exists()
