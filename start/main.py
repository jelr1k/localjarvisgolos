from __future__ import annotations

import logging
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent


def _find_project_root() -> Path:
    for candidate in (APP_DIR, APP_DIR.parent):
        if (candidate / "core").is_dir():
            return candidate
    return APP_DIR


PROJECT_ROOT = _find_project_root()
project_root = str(PROJECT_ROOT)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from PySide6.QtWidgets import QApplication, QMessageBox

from core.application import JarvisApplication
from core.app_paths import WORKSPACE_DIR
from services.model_service import ModelService
from services.statistics_service import StatisticsService
from tools.registry import TOOLS
from presentation.application_controller import ApplicationController
from presentation.alias_controller import AliasController
from presentation.chat_controller import ChatController
from presentation.dependency_controller import DependencyController
from presentation.ollama_controller import OllamaController
from presentation.settings_controller import SettingsController
from presentation.statistics_controller import StatisticsController
from presentation.tools_controller import ToolsController
from presentation.voice_controller import VoiceController
from presentation.wake_word_controller import WakeWordController
from presentation.workspace_controller import WorkspaceController
from core.logging_config import setup_logging
from ui.main_window import MainWindow


def main():
    logger = setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")

    backend = None
    try:
        backend = JarvisApplication()
        application_controller = ApplicationController(backend)
        chat_controller = ChatController(backend.chat_service, backend.events)
        voice_controller = VoiceController(backend.voice_service, backend.events)
        wake_word_controller = WakeWordController(backend.wake_word_detector, backend.events)
        dependency_controller = DependencyController(backend.dependency_manager, backend.events)
        settings_controller = SettingsController(backend.config, ModelService(backend.provider), dependency_controller, backend.tasks, backend.events, backend.voice_service, update_checker=backend.update_checker, update_service=backend.update_service)
        alias_controller = AliasController(backend.alias_manager)
        tools_controller = ToolsController(backend.permission_manager, TOOLS)
        ollama_controller = OllamaController(backend.ollama_manager, backend.tasks)
        statistics_controller = StatisticsController(StatisticsService(), ollama_controller, backend.tasks, backend.events)
        workspace_controller = WorkspaceController(WORKSPACE_DIR, backend.alias_manager)
        window = MainWindow(
            application_controller, chat_controller, voice_controller, wake_word_controller,
            dependency_controller, settings_controller, alias_controller, tools_controller,
            ollama_controller, statistics_controller, workspace_controller,
        )
        app.setApplicationName(backend.config.get("assistant_name", "JARVIS"))
        window.show()
        application_controller.start()
        logger.info("Jarvis frontend/backend started")
    except Exception as exc:
        logger.exception("Jarvis startup failed")
        if backend is not None:
            backend.shutdown()
        QMessageBox.critical(None, "Jarvis", str(exc))
        sys.exit(1)

    exit_code = app.exec()
    logging.getLogger("jarvis").info("Jarvis stopped")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
