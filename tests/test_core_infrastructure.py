from __future__ import annotations

from concurrent.futures import Future
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from core.background_task import BackgroundTask
from core.config_manager import ConfigManager, DEFAULTS
from core.dependency_manager import DependencyManager, ModelDownloadCancelled, _ProgressTqdm
from core.events import EventBus
from core.task_runner import TaskRunner
from core.version import APP_NAME, APP_VERSION, get_version
from core.workspace_index import WorkspaceIndex


def test_event_bus_subscribe_emit_and_unsubscribe():
    bus = EventBus()
    calls = []

    def handler(value, *, extra=None):
        calls.append((value, extra))

    bus.subscribe("demo", handler)
    bus.subscribe("demo", handler)
    bus.emit("demo", 42, extra="ok")
    bus.unsubscribe("demo", handler)
    bus.emit("demo", 99, extra="ignored")

    assert calls == [(42, "ok")]


def test_event_bus_handler_failure_does_not_break_other_handlers():
    bus = EventBus()
    calls = []

    def broken():
        raise RuntimeError("boom")

    bus.subscribe("demo", broken)
    bus.subscribe("demo", lambda: calls.append("ok"))
    bus.emit("demo")

    assert calls == ["ok"]


def test_task_runner_submit_and_reject_after_shutdown():
    runner = TaskRunner(max_workers=1)
    assert runner.submit(lambda: 2 + 3).result(timeout=2) == 5
    runner.shutdown(wait=True)
    with pytest.raises(RuntimeError, match="shut down"):
        runner.submit(lambda: None)
    runner.shutdown()


def test_background_task_uses_supplied_runner():
    runner = Mock()
    future = Future()
    runner.submit.return_value = future
    task = BackgroundTask(lambda: 123)

    result = task.submit(runner)

    assert result is future
    runner.submit.assert_called_once_with(task.function)


def test_config_manager_merges_nested_values_and_persists(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        '{"model":"test-model","voice":{"cpu_threads":8},"tools":{"open_url":false}}',
        encoding="utf-8",
    )

    config = ConfigManager(path)

    assert config.get("model") == "test-model"
    assert config.get("voice")["cpu_threads"] == 8
    assert config.get("voice")["language"] == DEFAULTS["voice"]["language"]
    assert config.get("tools")["open_url"] is False

    config.set("assistant_name", "TestJarvis")
    reloaded = ConfigManager(path)
    assert reloaded.get("assistant_name") == "TestJarvis"
    assert reloaded.ollama_url == DEFAULTS["ollama"]["base_url"]


def test_config_manager_recovers_from_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")

    config = ConfigManager(path)

    assert config.get("model") == DEFAULTS["model"]
    assert config.get("temperature") == DEFAULTS["temperature"]


def test_version_is_single_source_of_truth():
    assert APP_NAME == "JARVIS"
    assert get_version() == APP_VERSION


def test_dependency_progress_callback_is_not_bound_to_progress_instance():
    seen = []

    def callback(current, total, rate):
        seen.append((current, total, rate))

    bar = _ProgressTqdm(total=10)
    try:
        _ProgressTqdm.callback = callback
        _ProgressTqdm.cancel_event = None
        bar.update(3)
        assert seen
        assert seen[-1][0:2] == (3, 10)
        assert isinstance(seen[-1][2], float)
    finally:
        bar.close()
        _ProgressTqdm.callback = None
        _ProgressTqdm.cancel_event = None


def test_dependency_progress_honors_cancellation():
    import threading

    bar = _ProgressTqdm(total=1)
    try:
        _ProgressTqdm.cancel_event = threading.Event()
        _ProgressTqdm.cancel_event.set()
        with pytest.raises(ModelDownloadCancelled):
            bar._report()
    finally:
        bar.close()
        _ProgressTqdm.callback = None
        _ProgressTqdm.cancel_event = None


def test_dependency_manager_download_pipeline_is_mocked_and_emits_events():
    events = EventBus()
    observed = []
    for name in ("dependency.state_changed", "dependency.finished", "dependency.progress"):
        events.subscribe(name, lambda *args, _name=name: observed.append((_name, args)))

    manager = DependencyManager(events)
    manager.whisper_status = Mock(side_effect=["missing", "installed"])

    with patch("core.dependency_manager.snapshot_download", return_value=None) as download,          patch("core.dependency_manager.log_event"):
        assert manager.ensure_whisper_model("small") == "small"

    download.assert_called_once()
    assert ("dependency.state_changed", ("small", "downloading")) in observed
    assert ("dependency.state_changed", ("small", "installed")) in observed
    assert ("dependency.finished", ("small", True, "")) in observed


def test_dependency_manager_unknown_model_is_passthrough():
    manager = DependencyManager()
    assert manager.is_managed_whisper_model("tiny") is False
    assert manager.ensure_whisper_model("tiny") == "tiny"
    assert manager.whisper_download_size("tiny") == 0
    assert manager.whisper_status("tiny") == "unknown"


def test_workspace_index_refresh_and_category_search(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "readme.txt").write_text("x", encoding="utf-8")
    (tmp_path / "Steam.lnk").write_text("x", encoding="utf-8")
    (tmp_path / "folder").mkdir()

    index = WorkspaceIndex(tmp_path)

    assert len(index.entries()) == 3
    assert [entry.name for entry in index.search("readme.txt", ("files",), fuzzy=False)] == ["readme.txt"]
    assert [entry.name for entry in index.search("Steam", ("applications",), fuzzy=False)] == ["Steam.lnk"]
    assert [entry.name for entry in index.entries(("folders",))] == ["folder"]
