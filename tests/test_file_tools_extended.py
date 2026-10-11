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


def test_resolve_workspace_path_handles_nested_file(workspace):
    nested = workspace / "notes" / "draft.txt"
    nested.parent.mkdir(parents=True)
    nested.write_text("draft", encoding="utf-8")

    target, matches = paths.resolve_workspace_path("draft.txt", categories=("files",), fuzzy=False)

    assert target == nested.resolve()
    assert matches == [nested.resolve()]


def test_resolve_workspace_path_rejects_absolute_outside_workspace(workspace):
    outside = workspace.parent / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    target, matches = paths.resolve_workspace_path(str(outside), categories=("files",), fuzzy=False)

    assert target is None
    assert matches == []


def test_resolve_workspace_path_uses_fuzzy_workspace_match(workspace):
    target = workspace / "configuration.txt"
    target.write_text("cfg", encoding="utf-8")

    resolved, matches = paths.resolve_workspace_path("configuraton.txt", categories=("files",), fuzzy=True)

    assert resolved == target.resolve()
    assert matches == [target.resolve()]


def test_add_file_to_workspace_rejects_duplicate_destination(workspace, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")
    (workspace / "source.txt").write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError, match="уже существует"):
        paths.add_file_to_workspace(source)


def test_add_file_to_workspace_copies_external_file(workspace, tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("source", encoding="utf-8")

    target = paths.add_file_to_workspace(source)

    assert target == (workspace / "source.txt").resolve()
    assert target.read_text(encoding="utf-8") == "source"
