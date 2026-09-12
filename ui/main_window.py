from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMessageBox, QTabWidget, QVBoxLayout, QWidget

from services.model_service import ModelService
from services.statistics_service import StatisticsService
from ui.chat_page import ChatPage
from ui.ollama_page import OllamaPage
from ui.settings_page import SettingsPage
from ui.statistics_page import StatisticsPage
from ui.tools_page import ToolsPage


class MainWindow(QWidget):
    settings_applied = Signal()

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
        self.ollama_page = OllamaPage(config, ollama_manager)

        self.tabs.addTab(self.chat_page, "Чат")
        self.tabs.addTab(self.stats_page, "Генерация")
        self.tabs.addTab(self.settings_page, "Настройки")
        self.tabs.addTab(self.tools_page, "Инструменты")
        self.tabs.addTab(self.ollama_page, "Ollama")

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self.chat_service.chunk_received.connect(self.chat_page.on_chunk)
        self.chat_service.direct_response.connect(self.chat_page.on_direct_response)
        self.chat_service.generation_finished.connect(self.on_generation_finished)
        self.chat_service.error.connect(self.on_error)
        self.settings_page.settings_changed.connect(self._on_settings_changed)
        self.tools_page.tools_changed.connect(self.chat_service.refresh_tools)

        self.chat_page.update_model_label(self.config.get("model"))
        self.chat_page.update_assistant_name(self.config.get("assistant_name", "JARVIS"))
        self.chat_page.send_requested.connect(self.chat_service.send)

        self._on_settings_changed(
            self.config.get("model"),
            self.config.get("assistant_name", "JARVIS"),
        )

    def _on_settings_changed(self, model, assistant_name):
        self.chat_service.provider.set_base_url(self.config.ollama_url)
        self.ollama_manager.set_base_url(self.config.ollama_url)
        self.chat_page.update_model_label(model)
        self.chat_page.update_assistant_name(assistant_name)
        window = self.window()
        if window:
            window.setWindowTitle(assistant_name or "JARVIS")
        self.settings_applied.emit()

    def on_generation_finished(self, stats):
        self.stats_service.add(stats)
        self.stats_page.refresh(stats)
        self.chat_page.finish_generation()

    def on_error(self, error):
        self.chat_page.finish_generation()
        QMessageBox.critical(self, "Ошибка", error)
