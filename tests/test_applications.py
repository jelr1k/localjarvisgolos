from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import applications


class FakeProcess:
    def __init__(self, pid: int, children=None, parents=None):
        self.pid = pid
        self.terminated = False
        self._children = list(children or [])
        self._parents = list(parents or [])

    def children(self, recursive=False):
        self.children_recursive = recursive
        return list(self._children)

    def parents(self):
        return list(self._parents)

    def as_dict(self, attrs=None):
        info = {"pid": self.pid, "ppid": None, "name": None, "exe": None, "cmdline": None, "status": None, "username": None, "create_time": None}
        return {key: info[key] for key in (attrs or info.keys())}

    def terminate(self):
        self.terminated = True


class ApplicationToolTests(unittest.TestCase):
    def setUp(self):
        applications._PENDING_LAUNCH_CHOICES = []

    def tearDown(self):
        applications._PENDING_LAUNCH_CHOICES = []

    def test_process_matching_uses_resolved_executable(self):
        class Proc:
            def __init__(self, pid, name, exe):
                self.info = {"pid": pid, "name": name, "exe": exe}

        processes = [
            Proc(10, "prismlauncher.exe", r"C:\Apps\Prism\prismlauncher.exe"),
            Proc(11, "other.exe", r"C:\Apps\Other\other.exe"),
        ]

        with patch("tools.applications.psutil.process_iter", return_value=processes):
            matches = applications._running_process_matches(
                "Prism Launcher",
                executable=r"C:\Apps\Prism\prismlauncher.exe",
            )

        self.assertEqual([item["pid"] for item in matches], [10])

    def test_process_matching_ignores_exe_extension(self):
        class Proc:
            def __init__(self, pid, name, exe):
                self.info = {"pid": pid, "name": name, "exe": exe}

        processes = [
            Proc(20, "Geometry Dash", ""),
            Proc(21, "Other Game", r"C:\Games\Other\Other.exe"),
        ]

        with patch("tools.applications.psutil.process_iter", return_value=processes):
            matches = applications._running_process_matches(
                "Geometry Dash",
                executable=r"C:\Games\Geometry Dash\Geometry Dash.exe",
            )

        self.assertEqual([item["pid"] for item in matches], [20])

    def test_process_matching_normalizes_name_and_punctuation(self):
        class Proc:
            def __init__(self, pid, name, exe):
                self.info = {"pid": pid, "name": name, "exe": exe}

        processes = [Proc(30, '"Geometry-Dash.EXE"', "")]

        with patch("tools.applications.psutil.process_iter", return_value=processes):
            matches = applications._running_process_matches("geometry dash")

        self.assertEqual([item["pid"] for item in matches], [30])

    def test_close_application_accepts_already_closed_state(self):
        with patch("tools.applications._resolve_application", return_value={"success": True, "identity": {"normalized_executable": r"c:\apps\prism\prismlauncher.exe"}}), \
             patch("tools.applications._running_process_matches", return_value=[]):
            result = applications.close_application("Prism Launcher")

        self.assertTrue(result["success"])
        self.assertTrue(result["already_closed"])
        self.assertFalse(result["running"])

    def test_close_application_verifies_termination(self):
        fake = FakeProcess(123)

        with patch("tools.applications._resolve_application", return_value={"success": True, "identity": {"normalized_executable": r"c:\apps\prism\prismlauncher.exe"}}), \
             patch("tools.applications._running_process_matches", return_value=[{"pid": 123, "name": "prismlauncher.exe", "exe": r"C:\Apps\Prism\prismlauncher.exe"}]), \
             patch("tools.applications.psutil.Process", return_value=fake), \
             patch("tools.applications.psutil.wait_procs", return_value=([fake], [])):
            result = applications.close_application("Prism Launcher")

        self.assertTrue(fake.terminated)
        self.assertTrue(result["success"], result)
        self.assertFalse(result["running"], result)
        self.assertEqual(result["details"]["closed"], [123], result)

    def test_close_application_terminates_children_before_parent(self):
        child = FakeProcess(125)
        root = FakeProcess(123, children=[child])
        termination_order = []
        root.terminate = lambda: termination_order.append(root.pid)
        child.terminate = lambda: termination_order.append(child.pid)

        with patch("tools.applications._resolve_application", return_value={"success": True, "identity": {"normalized_executable": r"c:\apps\ddnet\ddnet.exe"}}), \
             patch("tools.applications._running_process_matches", return_value=[{"pid": 123, "name": "ddnet.exe", "exe": r"C:\Apps\DDNet\ddnet.exe"}]), \
             patch("tools.applications.psutil.Process", return_value=root), \
             patch("tools.applications.psutil.wait_procs", return_value=([child, root], [])):
            result = applications.close_application("DDNet")

        self.assertTrue(result["success"])
        self.assertEqual(termination_order, [125, 123])
        self.assertEqual(result["details"]["closed"], [125, 123])

    def test_close_application_uses_top_matched_process_as_tree_root(self):
        root = FakeProcess(123)
        child = FakeProcess(125, parents=[root])
        root._children = [child]
        termination_order = []
        root.terminate = lambda: termination_order.append(root.pid)
        child.terminate = lambda: termination_order.append(child.pid)

        processes_by_pid = {123: root, 125: child}
        matches = [
            {"pid": 123, "name": "geometry dash.exe", "exe": r"C:\Games\Geometry Dash\Geometry Dash.exe"},
            {"pid": 125, "name": "Geometry Dash", "exe": ""},
        ]

        with patch("tools.applications._resolve_application", return_value={"success": True, "identity": {"normalized_executable": r"c:\games\geometry dash\geometry dash.exe"}}), \
             patch("tools.applications._running_process_matches", return_value=matches), \
             patch("tools.applications.psutil.Process", side_effect=processes_by_pid.get), \
             patch("tools.applications.psutil.wait_procs", return_value=([child, root], [])):
            result = applications.close_application("Geometry Dash")

        self.assertTrue(result["success"])
        self.assertEqual(termination_order, [125, 123])
        self.assertEqual(result["details"]["closed"], [125, 123])

    def test_collect_process_tree_includes_all_descendants(self):
        grandchild = FakeProcess(127)
        child = FakeProcess(125, children=[grandchild])
        root = FakeProcess(123, children=[child])

        tree = applications._collect_process_tree(root)

        self.assertEqual([(proc.pid, depth) for proc, depth in tree], [(123, 0), (125, 1), (127, 2)])

    def test_single_workspace_match_launches_without_installed_app_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            shortcut = Path(tmp) / "Steam.lnk"
            shortcut.write_text("placeholder", encoding="utf-8")

            with patch("tools.applications.resolve_tool_path", return_value=(shortcut, [shortcut])), \
                 patch("tools.applications.find_application") as find_application, \
                 patch("tools.applications.os.startfile") as startfile:
                result = applications.launch_application("Steam")

        self.assertTrue(result["success"])
        self.assertEqual(result["path"], str(shortcut))
        find_application.assert_not_called()
        startfile.assert_called_once_with(str(shortcut))


    def test_installed_application_is_blocked_without_outside_workspace_permission(self):
        outside = Path(tempfile.gettempdir()) / "Steam.lnk"
        outside.write_text("placeholder", encoding="utf-8")
        with patch("tools.applications.find_application", return_value={"success": True, "path": str(outside)}), \
             patch("tools.applications.os.startfile") as startfile:
            result = applications.launch_application("Steam")

        self.assertFalse(result["success"])
        self.assertTrue(result["blocked"])
        self.assertTrue(result["outside_workspace"])
        self.assertIn("вне Workspace", result["error"])
        startfile.assert_not_called()

    def test_installed_application_can_launch_when_outside_workspace_is_allowed(self):
        outside = Path(tempfile.gettempdir()) / "Steam.lnk"
        outside.write_text("placeholder", encoding="utf-8")
        with patch("tools.applications.find_application", return_value={"success": True, "path": str(outside)}), \
             patch("tools.applications.os.startfile") as startfile:
            result = applications.launch_application("Steam", allow_outside_workspace=True)

        self.assertTrue(result["success"])
        startfile.assert_called_once_with(str(outside))

    def test_workspace_folder_can_be_opened(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "Games"
            folder.mkdir()

            with patch("tools.applications.resolve_tool_path", return_value=(folder, [folder])), \
                 patch("tools.applications.find_application") as find_application, \
                 patch("tools.applications.os.startfile") as startfile:
                result = applications.launch_application("Games")

        self.assertTrue(result["success"])
        self.assertEqual(result["path"], str(folder))
        find_application.assert_not_called()
        startfile.assert_called_once_with(str(folder))

    def test_multiple_workspace_matches_are_saved_for_numbered_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "Steam.lnk"
            second = Path(tmp) / "Steam.exe"
            first.write_text("placeholder", encoding="utf-8")
            second.write_text("placeholder", encoding="utf-8")

            with patch("tools.applications.resolve_tool_path", return_value=(None, [first, second])):
                result = applications.launch_application("Steam")

            self.assertFalse(result["success"])
            self.assertTrue(result["ambiguous"])
            self.assertEqual(result["matches"], [str(first), str(second)])
            self.assertIn(f"1. {first}", result["error"])
            self.assertIn(f"2. {second}", result["error"])
            self.assertTrue(applications.has_pending_launch_choices())

    def test_numbered_selection_launches_exact_selected_workspace_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "Steam.lnk"
            second = Path(tmp) / "Steam.exe"
            first.write_text("placeholder", encoding="utf-8")
            second.write_text("placeholder", encoding="utf-8")

            applications._PENDING_LAUNCH_CHOICES = [first, second]
            with patch("tools.applications.os.startfile") as startfile:
                result = applications.launch_application("2")

        self.assertTrue(result["success"])
        self.assertEqual(result["path"], str(second))
        startfile.assert_called_once_with(str(second))
        self.assertFalse(applications.has_pending_launch_choices())

    def test_invalid_number_keeps_pending_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "Steam.lnk"
            second = Path(tmp) / "Steam.exe"
            first.write_text("placeholder", encoding="utf-8")
            second.write_text("placeholder", encoding="utf-8")
            applications._PENDING_LAUNCH_CHOICES = [first, second]

            result = applications.launch_application("3")

        self.assertFalse(result["success"])
        self.assertTrue(result["ambiguous"])
        self.assertIn("от 1 до 2", result["error"])
        self.assertTrue(applications.has_pending_launch_choices())


    def test_selection_index_accepts_numeric_and_word_forms(self):
        self.assertEqual(applications._selection_index("9"), 9)
        self.assertEqual(applications._selection_index("четвёртый"), 4)
        self.assertIsNone(applications._selection_index("0"))
        self.assertIsNone(applications._selection_index("что-то"))

    def test_get_process_status_rejects_empty_name(self):
        result = applications.get_process_status("   ")
        self.assertFalse(result["success"])
        self.assertIn("название приложения", result["error"])

    def test_close_application_reports_process_creation_failure(self):
        with patch("tools.applications._resolve_application", return_value={
            "success": True,
            "identity": {"normalized_executable": r"c:\apps\test.exe"},
        }),              patch("tools.applications._running_process_matches", return_value=[{"pid": 123}]),              patch("tools.applications.psutil.Process", side_effect=OSError("denied")), \
             patch("tools.applications._log_process_snapshot"):
            result = applications.close_application("Test")

        self.assertFalse(result["success"])
        self.assertTrue(result["details"]["failed"])
        self.assertEqual(result["running"], False)

    def test_close_application_reports_processes_that_stay_alive(self):
        fake = FakeProcess(123)
        with patch("tools.applications._resolve_application", return_value={
            "success": True,
            "identity": {"normalized_executable": r"c:\apps\test.exe"},
        }),              patch("tools.applications._running_process_matches", return_value=[{"pid": 123}]),              patch("tools.applications.psutil.Process", return_value=fake),              patch("tools.applications.psutil.wait_procs", return_value=([], [fake])):
            result = applications.close_application("Test")

        self.assertFalse(result["success"])
        self.assertTrue(result["running"])
        self.assertTrue(result["details"]["failed"])
        self.assertTrue(fake.terminated)

    def test_minimize_application_fails_cleanly_without_win32(self):
        with patch("tools.applications.win32gui", None):
            result = applications.minimize_application("Steam")

        self.assertFalse(result["success"])
        self.assertIn("pywin32", result["error"])

    def test_open_url_rejects_invalid_scheme_before_startfile(self):
        with patch("tools.applications.os.startfile") as startfile:
            result = applications.open_url("ftp://example.com")

        self.assertFalse(result["success"])
        startfile.assert_not_called()

    def test_shortcut_resolution_returns_target_executable(self):
        class Shortcut:
            TargetPath = r"C:\Apps\Steam\steam.exe"
            WorkingDirectory = r"C:\Apps\Steam"
            Arguments = ""

        shell = Mock()
        shell.CreateShortcut.return_value = Shortcut()
        fake_win32com = Mock()
        fake_win32com.client.Dispatch.return_value = shell

        with patch("tools.applications.win32com", fake_win32com):
            result = applications._resolve_shortcut_target(Path(r"C:\Apps\Steam.lnk"))

        self.assertEqual(result, Path(r"C:\Apps\Steam\steam.exe").resolve())
        shell.CreateShortcut.assert_called_once()

    def test_shortcut_resolution_handles_missing_target(self):
        class Shortcut:
            TargetPath = ""

        shell = Mock()
        shell.CreateShortcut.return_value = Shortcut()
        fake_win32com = Mock()
        fake_win32com.client.Dispatch.return_value = shell

        with patch("tools.applications.win32com", fake_win32com):
            result = applications._resolve_shortcut_target(Path(r"C:\Apps\Steam.lnk"))

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
