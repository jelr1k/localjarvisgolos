from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from tools import applications


def test_normalize_executable_and_process_label():
    assert applications._normalize_process_label(r"C:\Games\Geometry-Dash.EXE") == "geometry dash"
    assert applications._normalize_executable(r"C:\Games\Tool.exe").endswith("tool.exe")


@pytest.mark.parametrize(
    ("target", "expected"),
    [("1", 1), ("первый", 1), ("вторая", 2), ("четвертый", 4), ("5.", 5), ("six", None)],
)
def test_selection_index(target, expected):
    assert applications._selection_index(target) == expected


def test_process_cmdline_matches_path_and_normalized_label():
    cmdline = [r"C:\Apps\Steam\steam.exe", "--silent"]
    assert applications._process_cmdline_matches(cmdline, r"c:\apps\steam\steam.exe")
    assert applications._process_cmdline_matches(["Steam.EXE"], r"C:\Apps\Steam\steam.exe")
    assert not applications._process_cmdline_matches(["other.exe"], r"C:\Apps\Steam\steam.exe")


def test_find_application_uses_start_menu_and_deduplicates_by_executable(tmp_path):
    root = tmp_path / "Programs"
    root.mkdir()
    shortcut = root / "one" / "Steam.lnk"
    duplicate = root / "two" / "Steam.lnk"
    shortcut.parent.mkdir()
    duplicate.parent.mkdir()
    shortcut.write_text("x", encoding="utf-8")
    duplicate.write_text("x", encoding="utf-8")
    exe = tmp_path / "Steam.exe"

    with patch.object(applications, "_WINDOWS_APP_DIRS", [root]),          patch.object(applications.shutil, "which", return_value=None),          patch.object(applications, "_resolve_shortcut_target", return_value=exe):
        result = applications.find_application("Steam")

    assert result["success"] is True
    assert result["path"] in {str(shortcut.resolve()), str(duplicate.resolve())}
    assert len(result["matches"]) == 2


def test_find_application_reports_missing_name():
    result = applications.find_application("   ")
    assert result["success"] is False


def test_open_url_validates_before_starting():
    with patch.object(applications.os, "startfile") as startfile:
        ok = applications.open_url("https://example.com")
        assert ok["success"] is True
        startfile.assert_called_once_with("https://example.com")

    bad = applications.open_url("file:///secret")
    assert bad["success"] is False


def test_application_resolver_can_use_workspace_executable(tmp_path):
    exe = tmp_path / "Tool.exe"
    exe.write_text("fake", encoding="utf-8")

    with patch.object(applications, "find_application", return_value={"success": False, "error": "missing"}),          patch.object(applications, "resolve_tool_path", return_value=(exe, [exe])):
        result = applications.ApplicationResolver().resolve("Tool", allow_workspace=True)

    assert result["success"] is True
    assert result["identity"]["target_executable"].endswith("Tool.exe")


def test_launch_invalid_selection_keeps_pending_choices():
    applications._PENDING_LAUNCH_CHOICES = [Path("one.exe"), Path("two.exe")]
    try:
        result = applications.launch_application("9")
        assert result["success"] is False
        assert result["ambiguous"] is True
        assert result["matches"] == ["one.exe", "two.exe"]
        assert applications._PENDING_LAUNCH_CHOICES == [Path("one.exe"), Path("two.exe")]
    finally:
        applications._PENDING_LAUNCH_CHOICES = []
