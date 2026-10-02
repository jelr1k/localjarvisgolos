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


class FakeUpdateService:
    def __init__(self, plan=None, error=None):
        self.plan = plan
        self.error = error
        self.calls = 0

    def prepare(self, info):
        self.calls += 1
        if self.error:
            raise self.error
        return self.plan


def make_controller(checker, update_service=None):
    return SettingsController(
        config=None,
        model_service=None,
        dependency_controller=None,
        task_runner=FakeTasks(),
        event_bus=FakeEvents(),
        voice_service=None,
        update_checker=checker,
        update_service=update_service,
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


def test_settings_controller_attaches_update_plan_to_available_update():
    from services.update_checker import ReleaseAsset, UpdateInfo

    info = UpdateInfo(
        current_version="0.1.0",
        latest_version="0.2.0",
        update_available=True,
        release_url="https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.2.0",
        tag_name="v0.2.0",
        release_name="JARVIS 0.2.0",
        assets=(
            ReleaseAsset(
                "JARVIS.zip",
                "https://github.com/jelr1k/localjarvisgolos/releases/download/v0.2.0/JARVIS.zip",
                2048,
            ),
        ),
    )
    plan = object()
    service = FakeUpdateService(plan=plan)
    controller = make_controller(FakeChecker(result=info), service)
    received = []

    controller.update_check_finished.connect(received.append)
    controller.check_for_update()

    assert service.calls == 1
    assert received[0]["success"] is True
    assert received[0]["info"] is info
    assert received[0]["plan"] is plan


def test_settings_controller_reports_update_plan_error():
    from services.update_checker import ReleaseAsset, UpdateInfo
    from services.update_service import UpdateServiceError

    info = UpdateInfo(
        current_version="0.1.0",
        latest_version="0.2.0",
        update_available=True,
        release_url="https://github.com/jelr1k/localjarvisgolos/releases/tag/v0.2.0",
        tag_name="v0.2.0",
        release_name="JARVIS 0.2.0",
        assets=(
            ReleaseAsset(
                "JARVIS.zip",
                "https://github.com/jelr1k/localjarvisgolos/releases/download/v0.2.0/JARVIS.zip",
                2048,
            ),
        ),
    )
    service = FakeUpdateService(error=UpdateServiceError("bad archive"))
    controller = make_controller(FakeChecker(result=info), service)
    received = []

    controller.update_check_finished.connect(received.append)
    controller.check_for_update()

    assert received[0]["success"] is False
    assert received[0]["error"] == "bad archive"
    assert received[0]["info"] is info
