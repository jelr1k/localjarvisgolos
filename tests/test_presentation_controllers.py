from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QCoreApplication

from core.events import EventBus
from presentation.alias_controller import AliasController
from presentation.application_controller import ApplicationController
from presentation.chat_controller import ChatController
from presentation.dependency_controller import DependencyController
from presentation.ollama_controller import OllamaController
from presentation.statistics_controller import StatisticsController
from presentation.tools_controller import ToolsController
from presentation.voice_controller import VoiceController
from presentation.workspace_controller import WorkspaceController
from services.statistics_service import StatisticsService


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    return app


class ImmediateRunner:
    def submit(self, function, *args, **kwargs):
        future = Future()
        try:
            future.set_result(function(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future


def test_alias_controller_delegates_and_emits_changed():
    manager = Mock()
    manager.list_objects.return_value = ["x"]
    manager.get_aliases.return_value = ["a"]
    manager.default_aliases.return_value = ["default"]
    controller = AliasController(manager)
    changed = []
    controller.changed.connect(lambda: changed.append(True))

    assert controller.list_objects() == ["x"]
    assert controller.get_aliases("files", "x") == ["a"]
    assert controller.default_aliases("files", "x") == ["default"]
    controller.set_aliases("files", "x", ["new"])
    controller.remove_object("files", "x")

    assert len(changed) == 2


def test_application_controller_delegates_and_reads_config():
    application = Mock()
    application.events = EventBus()
    application.config.get.return_value = "value"
    controller = ApplicationController(application)

    assert controller.config_value("key") == "value"
    controller.apply_settings()
    controller.start()
    controller.shutdown()

    application.apply_settings.assert_called_once()
    application.start.assert_called_once()
    application.shutdown.assert_called_once()
    controller.close()


def test_tools_controller_reads_and_updates_permissions():
    permission = Mock()
    permission.is_enabled.return_value = True
    tools = {"x": {"description": "test"}}
    controller = ToolsController(permission, tools)
    changed = []
    controller.changed.connect(lambda: changed.append(True))

    assert controller.tools() == tools
    assert controller.is_enabled("x") is True
    controller.set_enabled("x", False)

    permission.update.assert_called_once_with("x", False)
    assert changed == [True]


def test_dependency_and_voice_controllers_bridge_event_bus():
    events = EventBus()
    dependency = Mock()
    dep_controller = DependencyController(dependency, events)
    voice = Mock()
    voice.is_recording = False
    voice.transcribing.return_value = False
    voice_controller = VoiceController(voice, events)

    dep_seen = []
    voice_seen = []
    dep_controller.progress.connect(lambda *args: dep_seen.append(args))
    voice_controller.listening_changed.connect(lambda value: voice_seen.append(value))

    events.emit("dependency.progress", "small", 1, 2, 3.0)
    events.emit("voice.listening_changed", True)

    assert dep_seen == [("small", 1, 2, 3.0)]
    assert voice_seen == [True]

    assert dep_controller.whisper_status("small") == dependency.whisper_status("small")
    dep_controller.cancel()
    voice_controller.start()
    voice_controller.stop()
    voice_controller.apply_config({})
    voice_controller.close()
    dependency.cancel.assert_called_once()
    voice.start.assert_called_once()
    voice.stop.assert_called_once()
    voice.apply_config.assert_called_once_with({})


def test_chat_controller_forwards_events_and_calls():
    events = EventBus()
    service = Mock()
    service.router.command_catalog.return_value = ["command"]
    controller = ChatController(service, events)
    received = []
    controller.direct_response.connect(lambda text: received.append(text))

    events.emit("chat.direct_response", "hello")
    events.emit("chat.confirmation_requested", "delete_file", {"path": "x"})

    assert received == ["hello"]
    assert controller.command_catalog() == ["command"]
    controller.send("hi", True)
    controller.refresh_tools()
    controller.set_ui_actions({"minimize": lambda: None})
    controller.shutdown()
    controller.close()

    service.send.assert_called_once_with("hi", True)
    service.refresh_tools.assert_called_once()
    service.set_ui_actions.assert_called_once()
    service.shutdown.assert_called_once()


def test_ollama_controller_runs_actions_through_task_runner():
    manager = Mock()
    manager.started_by_jarvis = True
    manager.is_running.return_value = True
    manager.get_loaded_models.return_value = [{"name": "qwen"}]
    runner = ImmediateRunner()
    controller = OllamaController(manager, runner)
    finished = []
    controller.operation_finished.connect(lambda action, result: finished.append((action, result)))

    future = controller.run("status")
    assert future.result(timeout=1)["running"] is True
    assert controller.started_by_jarvis() is True
    assert controller.model_status("qwen") is not None
    assert finished[0][0] == "status"
    controller.run("unknown")
    assert finished[-1][1]["success"] is False


def test_statistics_controller_records_whisper_and_system_status():
    events = EventBus()
    service = StatisticsService()
    ollama = Mock()
    ollama.model_status.return_value = {"name": "qwen"}
    controller = StatisticsController(service, ollama, ImmediateRunner(), events)
    updates = []
    controller.whisper_updated.connect(lambda value: updates.append(value))

    controller.add({"tokens": 1})
    controller.add_whisper({"rtf": 2.0})
    events.emit("voice.whisper_stats", {"rtf": 1.0})

    assert service.latest == {"tokens": 1}
    assert controller.latest_whisper == {"rtf": 1.0}
    assert len(updates) == 2

    with patch("presentation.statistics_controller.psutil.cpu_percent", return_value=10.0),          patch("presentation.statistics_controller.psutil.virtual_memory", return_value=SimpleNamespace(used=1, total=2, percent=50.0)):
        result = controller.update_system_status("qwen").result(timeout=1).result() if False else controller.update_system_status("qwen").result(timeout=1)

    assert result["status"] == {"name": "qwen"}
    assert result["cpu"] == 10.0
    controller.close()


def test_workspace_controller_wraps_view_model(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    controller = WorkspaceController(workspace, Mock())

    assert controller.workspace == workspace.resolve()
    assert controller.refresh() == controller.model.refresh()
    controller.close() if hasattr(controller, "close") else None
