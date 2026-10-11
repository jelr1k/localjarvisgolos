from __future__ import annotations

import threading

from services.update_checker import UpdateInfo
from services.update_monitor import UpdateMonitor


class FakeChecker:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = 0

    def check(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


def make_info(available=False):
    return UpdateInfo(
        current_version="0.1.0",
        latest_version="0.2.0" if available else "0.1.0",
        update_available=available,
        release_url="https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.2.0",
        tag_name="v0.2.0" if available else "v0.1.0",
        release_name="JARVIS 0.2.0",
    )


def test_monitor_checks_in_background_and_reports_result():
    checker = FakeChecker(result=make_info(available=True))
    received = []
    ready = threading.Event()

    monitor = UpdateMonitor(
        checker=checker,
        interval_seconds=60,
        initial_delay_seconds=0,
        on_result=lambda result: (received.append(result), ready.set()),
    )

    monitor.start()
    assert ready.wait(timeout=2)
    monitor.stop()

    assert checker.calls == 1
    assert received[0]["success"] is True
    assert received[0]["info"].update_available is True
    assert not monitor.running


def test_monitor_reports_check_errors_without_crashing():
    checker = FakeChecker(error=RuntimeError("offline"))
    received = []
    ready = threading.Event()

    monitor = UpdateMonitor(
        checker=checker,
        interval_seconds=60,
        initial_delay_seconds=0,
        on_result=lambda result: (received.append(result), ready.set()),
    )

    monitor.start()
    assert ready.wait(timeout=2)
    monitor.stop()

    assert checker.calls == 1
    assert received[0]["success"] is False
    assert "offline" in received[0]["error"]


def test_monitor_does_not_start_twice():
    checker = FakeChecker(result=make_info())
    ready = threading.Event()

    monitor = UpdateMonitor(
        checker=checker,
        interval_seconds=60,
        initial_delay_seconds=0,
        on_result=lambda result: ready.set(),
    )

    monitor.start()
    monitor.start()
    assert ready.wait(timeout=2)
    monitor.stop()

    assert checker.calls == 1


def test_monitor_stop_cancels_initial_delay():
    checker = FakeChecker(result=make_info())
    monitor = UpdateMonitor(
        checker=checker,
        interval_seconds=60,
        initial_delay_seconds=60,
    )

    monitor.start()
    monitor.stop()

    assert checker.calls == 0
    assert not monitor.running
