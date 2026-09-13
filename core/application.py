from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from core.alias_manager import AliasManager
from core.config_manager import ConfigManager
from core.ollama_manager import OllamaManager
from core.app_paths import ensure_application_dirs
from llm.ollama import OllamaProvider
from services.chat_service import ChatService
from tools.paths import prepare_tool_workspace
from ui.main_window import MainWindow


class JarvisApplication(QMainWindow):
    def __init__(self):
        super().__init__()
        ensure_application_dirs()
        prepare_tool_workspace()

        self.config = ConfigManager()
        self.alias_manager = AliasManager()
        self.ollama_manager = OllamaManager(self.config.ollama_url)
        self.ollama_manager.start()

        self.provider = OllamaProvider(self.config.ollama_url)
        self.chat_service = ChatService(
            self.provider,
            self.config,
            self.ollama_manager,
            self.alias_manager,
        )
        self.ollama_manager.register_model(self.config.get("model"))

        self.window = MainWindow(
            self.chat_service,
            self.config,
            self.ollama_manager,
            self.alias_manager,
        )
        self.setCentralWidget(self.window)
        self.setWindowTitle(self.config.get("assistant_name", "JARVIS"))
        self.resize(1100, 750)

    def closeEvent(self, event):
        # GUI закрывается отдельно от Ollama Server. Модели освобождаем, сервер оставляем.
        self.ollama_manager.shutdown_for_app()
        event.accept()
