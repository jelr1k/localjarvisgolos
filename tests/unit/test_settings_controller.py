from __future__ import annotations

from concurrent.futures import Future

from presentation.settings_controller import SettingsController


class FakeEvents:
    def __init__(self):
        self.subscriptions = []

    def subscribe(self, event, handler):
        self.subscriptions.append((event, handler))

    def unsubscribe(self, event, handler):
        if (event, handler) in self.subscriptions:
            self.subscriptions.remove((event, handler))


class FakeTasks:
    def submit(self, function, *args, **kwargs):
        future = Future()
        try:
            future.set_result(function(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future


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


def make_controller(checker):
    return SettingsController(
        config=None,
        model_service=None,
        dependency_controller=None,
        task_runner=FakeTasks(),
        event_bus=FakeEvents(),
        voice_service=None,
        update_checker=checker,
    )


def test_settings_controller_emits_successful_update_check():
    checker = FakeChecker(result={"latest_version": "0.2.0"})
    controller = make_controller(checker)
    received = []

    controller.update_check_finished.connect(received.append)
    controller.check_for_update()

    assert checker.calls == 1
    assert received == [{"success": True, "info": {"latest_version": "0.2.0"}}]


def test_settings_controller_emits_update_check_error():
    checker = FakeChecker(error=RuntimeError("offline"))
    controller = make_controller(checker)
    received = []

    controller.update_check_finished.connect(received.append)
    controller.check_for_update()

    assert len(received) == 1
    assert received[0]["success"] is False
    assert "offline" in received[0]["error"]
