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
        """Минимальная psutil-совместимая диагностика для тестового процесса."""
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
        self.assertTrue(result["success"])
        self.assertFalse(result["running"])
        self.assertEqual(result["details"]["closed"], [123])

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

            with patch("tools.applications.resolve_tool_path", return_value=(None, [first, second])), \
                 patch("tools.applications.os.startfile") as startfile:
                result = applications.launch_application("Steam")
                self.assertFalse(result["success"])
                result = applications.launch_application("2")

        self.assertTrue(result["success"])
        self.assertEqual(result["path"], str(second))
        startfile.assert_called_once_with(str(second))
