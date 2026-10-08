from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def pytest_runtest_logreport(report):
    if report.when == "call" and report.failed:
        terminal = report.config.pluginmanager.getplugin("terminalreporter")
        if terminal is not None:
            terminal.write_line(f"DEBUG TEST FAILURE: {report.nodeid}")
            terminal.write_line(str(report.longrepr))
