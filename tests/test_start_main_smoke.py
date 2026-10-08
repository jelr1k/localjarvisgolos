from __future__ import annotations

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import Mock, patch

import pytest

import start.main as app_main


def test_start_main_happy_path_wires_backend_and_window():
    logger = Mock()
    app = Mock()
    app.exec.return_value = 0
    backend = Mock()
    backend.config.get.side_effect = lambda key, default=None: {
        "model": "qwen",
        "assistant_name": "JARVIS",
        "voice": {"wake_word": "Jarvis"},
    }.get(key, default)

    with patch.object(app_main, "setup_logging", return_value=logger),          patch.object(app_main, "QApplication", return_value=app),          patch.object(app_main, "JarvisApplication", return_value=backend),          patch.object(app_main, "ApplicationController", return_value=Mock()),          patch.object(app_main, "ChatController", return_value=Mock()),          patch.object(app_main, "VoiceController", return_value=Mock()),          patch.object(app_main, "WakeWordController", return_value=Mock()),          patch.object(app_main, "DependencyController", return_value=Mock()),          patch.object(app_main, "SettingsController", return_value=Mock()),          patch.object(app_main, "AliasController", return_value=Mock()),          patch.object(app_main, "ToolsController", return_value=Mock()),          patch.object(app_main, "OllamaController", return_value=Mock()),          patch.object(app_main, "StatisticsController", return_value=Mock()),          patch.object(app_main, "WorkspaceController", return_value=Mock()),          patch.object(app_main, "MainWindow", return_value=Mock()),          patch.object(app_main.sys, "exit", side_effect=SystemExit(0)):
        with pytest.raises(SystemExit, match="0"):
            app_main.main()

    app.setApplicationName.assert_any_call("Jarvis")
    app.exec.assert_called_once()
    logger.info.assert_called()


def test_start_main_startup_error_shuts_backend_down_and_exits():
    logger = Mock()
    backend = Mock()

    with patch.object(app_main, "setup_logging", return_value=logger),          patch.object(app_main, "QApplication", return_value=Mock()),          patch.object(app_main, "JarvisApplication", return_value=backend),          patch.object(app_main, "ApplicationController", side_effect=RuntimeError("startup boom")),          patch.object(app_main.QMessageBox, "critical"),          patch.object(app_main.sys, "exit", side_effect=SystemExit(1)):
        with pytest.raises(SystemExit, match="1"):
            app_main.main()

    backend.shutdown.assert_called_once()
