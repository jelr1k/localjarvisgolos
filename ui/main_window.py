from PySide6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QMessageBox

from services.model_service import ModelService
from services.statistics_service import StatisticsService
from ui.chat_page import ChatPage
from ui.statistics_page import StatisticsPage
from ui.settings_page import SettingsPage
from ui.tools_page import ToolsPage


class MainWindow(QWidget):
    def __init__(self, chat_service, config, ollama_manager):
        super().__init__()
        self.chat_service = chat_service
        self.config = config
        self.ollama_manager = ollama_manager
        self.model_service = ModelService(chat_service.provider)
        self.stats_service = StatisticsService()

        self.tabs = QTabWidget()
        self.chat_page = ChatPage(chat_service, config)
        self.stats_page = StatisticsPage(self.stats_service, self.ollama_manager)
        self.settings_page = SettingsPage(config, self.model_service)
        self.tools_page = ToolsPage(config)

        self.tabs.addTab(self.chat_page, "Чат")
        self.tabs.addTab(self.stats_page, "Генерация")
        self.tabs.addTab(self.settings_page, "Настройки")
        self.tabs.addTab(self.tools_page, "Инструменты")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self.chat_service.chunk_received.connect(self.chat_page.on_chunk)
        self.chat_service.generation_finished.connect(self.on_generation_finished)
        self.chat_service.error.connect(self.on_error)
        self.settings_page.settings_changed.connect(self.chat_page.update_settings)
        self.tools_page.tools_changed.connect(self.chat_service.refresh_tools)

        self.chat_page.update_model_label(self.config.get("model"))
        self.chat_page.send_requested.connect(self.chat_service.send)

    def on_generation_finished(self, stats):
        self.stats_service.add(stats)
        self.stats_page.refresh(stats)
        self.chat_page.finish_generation()

    def on_error(self, error):
        self.chat_page.finish_generation()
        QMessageBox.critical(self, "Ошибка", error)
