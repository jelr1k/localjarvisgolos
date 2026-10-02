from __future__ import annotations

from concurrent.futures import Future

from core.app_paths import APP_ROOT, CONFIG_FILE, LOG_DIR, RESOURCE_ROOT, WORKSPACE_DIR, get_application_root, get_resource_root
from core.config_manager import ConfigManager, DEFAULTS
from core.events import EventBus
from core.task_runner import TaskRunner
from core.version import APP_NAME, APP_VERSION, get_version


def test_version_is_single_semantic_value():
    assert APP_NAME == "JARVIS"
    assert get_version() == APP_VERSION
    parts = APP_VERSION.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


def test_application_paths_are_rooted_in_project():
    assert get_application_root() == APP_ROOT
    assert get_resource_root() == RESOURCE_ROOT
    assert WORKSPACE_DIR.is_relative_to(APP_ROOT)
    assert LOG_DIR.is_relative_to(APP_ROOT)
    assert CONFIG_FILE.parent.name == "Jarvis"


def test_config_manager_merges_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text('{"assistant_name": "Test", "ollama": {"base_url": "http://example"}}', encoding="utf-8")

    config = ConfigManager(path)

    assert config.get("assistant_name") == "Test"
    assert config.get("model") == DEFAULTS["model"]
    assert config.ollama_url == "http://example"


def test_config_manager_persists_changes(tmp_path):
    path = tmp_path / "settings.json"
    config = ConfigManager(path)
    config.set("assistant_name", "JARVIS Test")

    reloaded = ConfigManager(path)
    assert reloaded.get("assistant_name") == "JARVIS Test"


def test_event_bus_subscribe_emit_and_unsubscribe():
    events = EventBus()
    received = []

    def handler(value):
        received.append(value)

    events.subscribe("test", handler)
    events.emit("test", 42)
    events.unsubscribe("test", handler)
    events.emit("test", 99)

    assert received == [42]


def test_event_bus_does_not_stop_other_handlers_after_one_fails():
    events = EventBus()
    received = []

    def broken():
        raise RuntimeError("expected")

    def healthy():
        received.append("ok")

    events.subscribe("test", broken)
    events.subscribe("test", healthy)
    events.emit("test")

    assert received == ["ok"]


def test_task_runner_runs_background_task():
    runner = TaskRunner(max_workers=1)
    try:
        future = runner.submit(lambda: 2 + 3)
        assert isinstance(future, Future)
        assert future.result(timeout=2) == 5
    finally:
        runner.shutdown(wait=True)


def test_task_runner_rejects_work_after_shutdown():
    runner = TaskRunner(max_workers=1)
    runner.shutdown(wait=True)

    try:
        runner.submit(lambda: None)
    except RuntimeError as exc:
        assert "shut down" in str(exc)
    else:
        raise AssertionError("TaskRunner accepted work after shutdown")
