from __future__ import annotations

import logging

from PySide6.QtWidgets import QApplication, QMainWindow

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
        try:
            # Ollama is needed only for LLM requests. A missing server must not
            # prevent Jarvis from starting and handling direct local commands.
            self.ollama_manager.start()
        except RuntimeError as exc:
            logger.warning("ollama_start_at_boot_failed error=%s", exc)

        self.provider = OllamaProvider(self.config.ollama_url)
        self.chat_service = ChatService(self.provider, self.config, self.ollama_manager, self.alias_manager)
        self.ollama_manager.register_model(self.config.get("model"))

        self.window = MainWindow(self.chat_service, self.config, self.ollama_manager, self.alias_manager)
        self.setCentralWidget(self.window)
        self.setWindowTitle(self.config.get("assistant_name", "JARVIS"))
        self.resize(1100, 750)
        logger.info("application_init_finish title=%r size=%sx%s model=%s", self.windowTitle(), self.width(), self.height(), self.config.get("model"))
        self._shutdown_started = False\n        self._close_cleanup_started = False

    def shutdown(self) -> None:
        """Полностью завершает Jarvis, включая его главное окно и Qt event loop."""
        if self._shutdown_started:
            return

        self._shutdown_started = True
        logger.info("application_shutdown_requested")

        try:
            # MainWindow владеет голосовыми компонентами. Его closeEvent
            # останавливает Wake Word и VoiceController.
            self.window.close()
            logger.info("application_main_window_closed")
        except Exception:
            logger.exception("application_main_window_close_failed")

        try:
            # Закрываем само верхнеуровневое окно. Это также запускает
            # application-level cleanup в closeEvent().
            self.close()
            logger.info("application_top_level_window_closed")
        except Exception:
            logger.exception("application_top_level_window_close_failed")

        app = QApplication.instance()
        if app is not None:
            logger.info("application_qt_quit_requested")
            app.quit()

    def closeEvent(self, event):
        logger.info("application_close_start")
        try:
            self.ollama_manager.shutdown_for_app()
            logger.info("application_close_cleanup_finish")
        except Exception:
            logger.exception("application_close_cleanup_failed")
        event.accept()
        logger.info("application_close_finish")
