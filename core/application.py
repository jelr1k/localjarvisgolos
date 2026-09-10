from PySide6.QtWidgets import QMainWindow

from core.config_manager import ConfigManager
from core.ollama_manager import OllamaManager

from llm.ollama import OllamaProvider

from services.chat_service import ChatService
from tools.paths import prepare_tool_workspace

from ui.main_window import MainWindow


class JarvisApplication(QMainWindow):
    def __init__(self):
        super().__init__()

        self.config = ConfigManager()
        prepare_tool_workspace()

        self.ollama_manager = OllamaManager(
            self.config.ollama_url
        )

        # Проверяем / запускаем Ollama
        self.ollama_manager.start()

        self.provider = OllamaProvider(
            self.config.ollama_url
        )

        self.chat_service = ChatService(
            self.provider,
            self.config
        )

        # Запоминаем текущую модель.
        self.ollama_manager.register_model(
            self.config.get("model")
        )

        self.window = MainWindow(
            self.chat_service,
            self.config,
            self.ollama_manager
        )

        self.setCentralWidget(
            self.window
        )

        self.setWindowTitle("JARVIS")

        self.resize(
            1100,
            750
        )

    def closeEvent(self, event):
        # Выгружаем модель и корректно
        # завершаем Ollama.
        self.ollama_manager.stop()

        event.accept()
