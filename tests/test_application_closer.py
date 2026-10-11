from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

from tools import application_closer


def test_close_application_reports_already_closed_when_no_process_matches():
    with patch.object(application_closer, "_resolve_executable", return_value=(Path("C:/Apps/Tool.exe"), [Path("Tool.lnk")])),          patch.object(application_closer._applications, "_running_process_matches", return_value=[]):
        result = application_closer.close_application("Tool")

    assert result["success"] is True
    assert result["running"] is False
    assert result["already_closed"] is True
    assert result["details"] == {"closed": [], "failed": []}


def test_close_application_reports_ambiguous_resolution():
    matches = [Path("one.lnk"), Path("two.lnk")]
    with patch.object(application_closer, "_resolve_executable", return_value=(None, matches)):
        result = application_closer.close_application("Tool")

    assert result["success"] is False
    assert result["ambiguous"] is True
    assert result["matches"] == ["one.lnk", "two.lnk"]


def test_close_application_terminates_process_tree():
    root = Mock(pid=10)
    child = Mock(pid=11)

    with patch.object(application_closer, "_resolve_executable", return_value=(Path("C:/Apps/Tool.exe"), [])),          patch.object(application_closer._applications, "_running_process_matches", return_value=[{"pid": 10}]),          patch("tools.application_closer.psutil.Process", return_value=root),          patch.object(application_closer._applications, "_select_process_roots", return_value=[root]),          patch.object(application_closer._applications, "_collect_process_tree", return_value=[(root, 0), (child, 1)]),          patch("tools.application_closer.psutil.wait_procs", return_value=([root, child], [])):
        result = application_closer.close_application("Tool")

    root.terminate.assert_called_once()
    child.terminate.assert_called_once()
    assert result["success"] is True
    assert set(result["details"]["closed"]) == {10, 11}


def test_close_application_kills_processes_that_ignore_terminate():
    process = Mock(pid=10)

    with patch.object(application_closer, "_resolve_executable", return_value=(Path("C:/Apps/Tool.exe"), [])),          patch.object(application_closer._applications, "_running_process_matches", return_value=[{"pid": 10}]),          patch("tools.application_closer.psutil.Process", return_value=process),          patch.object(application_closer._applications, "_select_process_roots", return_value=[process]),          patch.object(application_closer._applications, "_collect_process_tree", return_value=[(process, 0)]),          patch("tools.application_closer.psutil.wait_procs", side_effect=[([], [process]), ([process], [])]):
        result = application_closer.close_application("Tool")

    process.terminate.assert_called_once()
    process.kill.assert_called_once()
    assert result["success"] is True
    assert result["details"]["closed"] == [10]


def test_close_application_records_process_access_failures():
    process = Mock(pid=10)
    process.terminate.side_effect = PermissionError("denied")

    with patch.object(application_closer, "_resolve_executable", return_value=(Path("C:/Apps/Tool.exe"), [])),          patch.object(application_closer._applications, "_running_process_matches", return_value=[{"pid": 10}]),          patch("tools.application_closer.psutil.Process", return_value=process),          patch.object(application_closer._applications, "_select_process_roots", return_value=[process]),          patch.object(application_closer._applications, "_collect_process_tree", return_value=[(process, 0)]),          patch("tools.application_closer.psutil.wait_procs", side_effect=[([], [process]), ([], [process])]):
        process.kill.side_effect = PermissionError("kill denied")
        result = application_closer.close_application("Tool")

    assert result["success"] is False
    assert result["details"]["failed"]
    assert "Tool" in result["error"]
