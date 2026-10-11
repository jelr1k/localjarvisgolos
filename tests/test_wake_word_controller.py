from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from core.events import EventBus
from presentation.wake_word_controller import WakeWordController


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is not None:
        return app
    return QApplication([])


def test_wake_word_controller_bridges_events_and_service_calls():
    events = EventBus()
    service = Mock()
    service.is_running.return_value = True
    controller = WakeWordController(service, events)

    detected = []
    recognized = []
    listening = []
    statuses = []
    errors = []

    controller.detected.connect(detected.append)
    controller.recognized.connect(recognized.append)
    controller.listening_changed.connect(listening.append)
    controller.status.connect(statuses.append)
    controller.error.connect(errors.append)

    events.emit("wake_word.detected", "Jarvis")
    events.emit("wake_word.recognized", "джарвис")
    events.emit("wake_word.listening_changed", True)
    events.emit("wake_word.status", "слушаю")
    events.emit("wake_word.error", "boom")

    assert detected == ["Jarvis"]
    assert recognized == ["джарвис"]
    assert listening == [True]
    assert statuses == ["слушаю"]
    assert errors == ["boom"]

    controller.start()
    controller.stop()
    controller.restart()
    controller.apply_config({"voice": {"wake_word": "Jarvis"}})
    assert controller.is_running() is True
    controller.close()

    service.start.assert_called_once()
    service.stop.assert_called_once()
    service.restart.assert_called_once()
    service.apply_config.assert_called_once()
    service.is_running.assert_called_once()
    service.close.assert_called_once()
