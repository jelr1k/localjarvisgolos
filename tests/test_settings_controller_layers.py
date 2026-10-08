from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from concurrent.futures import Future
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication

from core.events import EventBus
from services.statistics_service import StatisticsService
from services.update_service import UpdateServiceError
from presentation.settings_controller import SettingsController


@pytest.fixture(scope="session", autouse=True)
def qapp():
    return QCoreApplication.instance() or QCoreApplication([])


class ImmediateRunner:
    def submit(self, function, *args, **kwargs):
        future = Future()
        try:
            future.set_result(function(*args, **kwargs))
        except Exception as exc:
            future.set_exception(exc)
        return future


class ConfigStub:
    def __init__(self):
        self.data = {
            "assistant_name": "Jarvis",
            "model": "qwen",
            "temperature": 0.7,
            "context_length": 4096,
            "max_tokens": 128,
            "router_only_mode": False,
            "allow_outside_workspace": False,
            "voice": {},
            "ollama": {"base_url": "http://localhost:11434"},
            "rofl": {"chance": 0.12, "demon_chance": 0.15},
        }
        self.saved = 0

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def ollama_url(self):
        return self.data["ollama"]["base_url"]

    def save(self):
        self.saved += 1


def make_controller(**overrides):
    config = ConfigStub()
    defaults = dict(
        model_service=Mock(),
        dependency_controller=Mock(),
        task_runner=ImmediateRunner(),
        event_bus=EventBus(),
        voice_service=Mock(),
        update_checker=Mock(),
        update_service=Mock(),
        update_downloader=Mock(),
        update_validator=Mock(),
        update_backup=Mock(),
        update_relauncher=Mock(),
    )
    defaults.update(overrides)
    controller = SettingsController(config, **defaults)
    return controller, config


def test_statistics_service_latest_and_whisper_history():
    service = StatisticsService()

    assert service.latest is None
    assert service.latest_whisper is None

    service.add({"tokens": 1})
    service.add({"tokens": 2})
    service.add_whisper(None)
    service.add_whisper({"rtf": 1.5})

    assert service.latest == {"tokens": 2}
    assert service.latest_whisper == {"rtf": 1.5}


def test_settings_controller_rofl_values_are_clamped_and_persisted():
    controller, config = make_controller()

    result = controller.save_rofl_settings(2, -1)

    assert result == {"chance": 1.0, "demon_chance": 0.0}
    assert config.saved == 1
    assert controller.get_rofl_settings() == result
    controller.close()


def test_settings_controller_prepare_update_without_update_keeps_result():
    controller, _ = make_controller()
    info = SimpleNamespace(update_available=False)

    result = controller._prepare_update_result({"success": True, "info": info})

    assert result["info"] is info
    assert "plan" not in result
    controller.close()


def test_settings_controller_prepare_update_builds_plan():
    controller, _ = make_controller()
    info = SimpleNamespace(update_available=True)
    plan = SimpleNamespace(target_version="0.2.0")
    controller._update_service.prepare.return_value = plan

    result = controller._prepare_update_result({"success": True, "info": info})

    assert result["plan"] is plan
    controller._update_service.prepare.assert_called_once_with(info)
    controller.close()


def test_settings_controller_prepare_update_maps_service_error():
    controller, _ = make_controller()
    info = SimpleNamespace(update_available=True)
    controller._update_service.prepare.side_effect = UpdateServiceError("bad plan")

    result = controller._prepare_update_result({"success": True, "info": info})

    assert result["success"] is False
    assert result["info"] is info
    assert "bad plan" in result["error"]
    controller.close()


def test_settings_controller_check_for_update_emits_plan():
    controller, _ = make_controller()
    info = SimpleNamespace(
        update_available=True,
        current_version="0.1.0",
        latest_version="0.2.0",
        release_name="Release",
        release_url="https://example.test/release",
    )
    plan = SimpleNamespace(target_version="0.2.0")
    controller._update_checker.check.return_value = info
    controller._update_service.prepare.return_value = plan

    finished = []
    confirmations = []
    controller.update_check_finished.connect(finished.append)
    controller.update_confirmation_requested.connect(confirmations.append)

    future = controller.check_for_update()

    assert future.result(timeout=1)["plan"] is plan
    assert finished and finished[-1]["plan"] is plan
    assert confirmations == [plan]
    controller.close()


def test_settings_controller_download_validation_backup_relaunch_chain():
    controller, _ = make_controller()
    plan = SimpleNamespace(target_version="0.2.0")
    download = SimpleNamespace(archive_path=Path("JARVIS.zip"), expected_size=10)
    validation = SimpleNamespace(file_count=3, total_uncompressed_size=30)
    backup = SimpleNamespace(backup_directory=Path("backup"), application_backup=Path("backup/app"))

    controller._update_downloader.download.return_value = download
    controller._update_validator.validate.return_value = validation
    controller._update_backup.create_backup.return_value = backup
    controller._update_relauncher.prepare.return_value = SimpleNamespace(command=["updater"])
    controller._update_relauncher.launch.return_value = SimpleNamespace(pid=123)

    validation_events = []
    backup_events = []
    restart_events = []
    controller.update_validation_finished.connect(validation_events.append)
    controller.update_backup_finished.connect(backup_events.append)
    controller.update_restart_requested.connect(restart_events.append)

    controller.download_update(plan)

    assert validation_events[-1]["success"] is True
    assert backup_events[-1]["success"] is True
    assert restart_events[-1]["success"] is True
    controller._update_downloader.download.assert_called_once()
    controller._update_validator.validate.assert_called_once_with(Path("JARVIS.zip"), 10)
    controller._update_relauncher.launch.assert_called_once()
    controller.close()


def test_settings_controller_save_updates_config_and_voice():
    controller, config = make_controller()
    controller._voice.apply_config.reset_mock()

    values = {
        "assistant_name": "NewJarvis",
        "model": "new-model",
        "temperature": 0.2,
        "context_length": 8192,
        "max_tokens": 256,
        "router_only_mode": True,
        "allow_outside_workspace": True,
        "ollama_url": "http://example.test",
        "voice": {"cpu_threads": 8},
    }

    result = controller.save(values)

    assert result == ("new-model", "NewJarvis")
    assert config.data["router_only_mode"] is True
    assert config.data["ollama"]["base_url"] == "http://example.test"
    assert config.data["voice"]["cpu_threads"] == 8
    assert config.saved == 1
    controller._voice.apply_config.assert_called_once_with(config.data)
    controller.close()


def test_settings_controller_validates_download_result_and_cleans_on_failure():
    controller, _ = make_controller()
    download = SimpleNamespace(archive_path=Path("bad.zip"), expected_size=1)
    controller._update_validator.validate.side_effect = Exception("broken")

    with pytest.raises(Exception, match="broken"):
        controller._validate_download_result(download)

    controller.close()


def test_settings_controller_relauncher_requires_download_and_backup():
    controller, _ = make_controller()

    with pytest.raises(Exception, match="Архив обновления"):
        controller._launch_update_relauncher()

    controller._download_result = SimpleNamespace(archive_path=Path("x.zip"), expected_size=1)
    with pytest.raises(Exception, match="Резервная копия"):
        controller._launch_update_relauncher()

    controller.close()
