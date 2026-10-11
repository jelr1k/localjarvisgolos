from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from ui.chat_page import ChatPage
from ui.settings_page import SettingsPage
from ui.statistics_page import StatisticsPage
from ui.tools_page import ToolsPage


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


def make_settings_controller():
    controller = Mock()
    values = {
        "assistant_name": "JARVIS",
        "model": "qwen3:1.7b",
        "temperature": 0.7,
        "context_length": 4096,
        "max_tokens": 128,
        "router_only_mode": False,
        "allow_outside_workspace": False,
        "voice": {
            "cpu_threads": 4,
            "beam_size": 1,
            "vad_filter": True,
            "without_timestamps": True,
            "condition_on_previous_text": False,
            "wake_word_enabled": True,
            "wake_word": "Jarvis",
            "silence_duration": 2.0,
            "model": "small",
        },
    }
    controller.get.side_effect = lambda key, default=None: values.get(key, default)
    controller.ollama_url = "http://localhost:11434"
    controller.list_microphones.return_value = {"success": False, "error": "smoke"}
    return controller


def test_core_pages_construct_in_offscreen_qt(app):
    chat = ChatPage(make_settings_controller())
    settings = SettingsPage(make_settings_controller())

    statistics_controller = Mock()
    statistics_controller.latest_whisper = None
    stats = StatisticsPage(statistics_controller)

    tools_controller = Mock()
    tools_controller.tools.return_value = {"read_file": {"description": "read"}}
    tools_controller.is_enabled.return_value = True
    tools_controller.workspace = "C:/Workspace"
    tools = ToolsPage(tools_controller)

    for widget in (chat, settings, stats, tools):
        widget.show()
        widget.hide()
        assert widget.isWidgetType()

    app.processEvents()
