from __future__ import annotations

import logging

from PySide6.QtWidgets import QMainWindow

from core.alias_manager import AliasManager
from core.config_manager import ConfigManager
from core.ollama_manager import OllamaManager
from core.app_paths import ensure_application_dirs
from llm.ollama import OllamaProvider
from services.chat_service import ChatService
from tools.paths import prepare_tool_workspace
from ui.main_window import MainWindow


logger = logging.getLogger("jarvis.application")


class JarvisApplication(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("application_init_start")
        ensure_application_dirs()
        prepare_tool_workspace()

        self.config = ConfigManager()
        logger.debug("config_loaded settings=%r", getattr(self.config, "settings", None))
        self.alias_manager = AliasManager()
        logger.debug("alias_manager_created")
        self.ollama_manager = OllamaManager(self.config.ollama_url)
        self.ollama_manager.start()

        self.provider = OllamaProvider(self.config.ollama_url)
        self.chat_service = ChatService(self.provider, self.config, self.ollama_manager, self.alias_manager)
        self.ollama_manager.register_model(self.config.get("model"))

        self.window = MainWindow(self.chat_service, self.config, self.ollama_manager, self.alias_manager)
        self.setCentralWidget(self.window)
        self.setWindowTitle(self.config.get("assistant_name", "JARVIS"))
        self.resize(1100, 750)
        logger.info("application_init_finish title=%r size=%sx%s model=%s", self.windowTitle(), self.width(), self.height(), self.config.get("model"))

    def closeEvent(self, event):
        logger.info("application_close_start")
        try:
            self.ollama_manager.shutdown_for_app()
            logger.info("application_close_cleanup_finish")
        except Exception:
            logger.exception("application_close_cleanup_failed")
        event.accept()
        logger.info("application_close_finish")
