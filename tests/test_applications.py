from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import applications


class FakeProcess:
    def __init__(self, pid: int):
        self.pid = pid
        self.terminated = False

    def terminate(self):
        self.terminated = True


class ApplicationToolTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
