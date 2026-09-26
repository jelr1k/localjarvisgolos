from __future__ import annotations

import logging

from PySide6.QtCore import Signal, QTimer
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton, QTabWidget, QVBoxLayout, QWidget

from core.alias_manager import AliasManager
from core.app_paths import WORKSPACE_DIR
from services.model_service import ModelService
from services.statistics_service import StatisticsService
from ui.alias_page import AliasPage
from ui.chat_page import ChatPage
from ui.commands_window import CommandsWindow
from ui.ollama_page import OllamaPage
from ui.settings_page import SettingsPage
from ui.statistics_page import StatisticsPage
from ui.tools_page import ToolsPage
from ui.workspace_tab import WorkspaceTab
from presentation.chat_controller import ChatController
from presentation.dependency_controller import DependencyController
from presentation.voice_controller import VoiceController
from presentation.wake_word_controller import WakeWordController


logger = logging.getLogger("jarvis.ui")


class MainWindow(QWidget):
    settings_applied = Signal()

    def __init__(self, application):
        super().__init__()
        self.application = application
        self.config = application.config
        self.chat_service = application.chat_service
        self.ollama_manager = application.ollama_manager
        self.alias_manager = application.alias_manager
        self.model_service = ModelService(self.chat_service.provider)
        self.stats_service = StatisticsService()

        self.chat_controller = ChatController(self.chat_service, application.events)
        self.voice_controller = VoiceController(application.voice_controller, application.events)
        self.wake_word_detector = WakeWordController(application.wake_word_detector, application.events)
        self.dependency_controller = DependencyController(
            application.dependency_manager,
            application.events,
        )

        self.tabs = QTabWidget()
        self.chat_page = ChatPage(self.chat_service, self.config)
        self.stats_page = StatisticsPage(self.stats_service, self.ollama_manager)
        self.settings_page = SettingsPage(
            self.config,
            self.model_service,
            self.dependency_controller,
        )
        self.alias_page = AliasPage(self.alias_manager)
        self.workspace_page = WorkspaceTab(WORKSPACE_DIR, self.alias_manager)
        self.tools_page = ToolsPage(self.config)
        self.ollama_page = OllamaPage(self.config, self.ollama_manager)
        self.commands_window = None
        self.commands_button = QPushButton("Команды")
        self.commands_button.clicked.connect(self.show_commands_window)

        for page, title in (
            (self.chat_page, "Чат"),
            (self.stats_page, "Генерация"),
            (self.settings_page, "Настройки"),
            (self.alias_page, "Алиасы"),
            (self.workspace_page, "Workspace"),
            (self.tools_page, "Инструменты"),
            (self.ollama_page, "Ollama"),
        ):
            self.tabs.addTab(page, title)

        top_bar = QHBoxLayout()
        top_bar.addStretch()
        top_bar.addWidget(self.commands_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_bar)
        layout.addWidget(self.tabs)

        self.chat_service.set_ui_actions({
            "shutdown": self.shutdown,
            "minimize": self.minimize_window,
            "maximize": self.maximize_window,
            "restore": self.restore_window,
        })

        self.chat_controller.chunk_received.connect(self.chat_page.on_chunk)
        self.chat_controller.direct_response.connect(self.chat_page.on_direct_response)
        self.chat_controller.generation_finished.connect(self.on_generation_finished)
        self.chat_controller.error.connect(self.on_error)
        self.settings_page.settings_changed.connect(self._on_settings_changed)
        self.tools_page.tools_changed.connect(self.chat_controller.refresh_tools)

        self.chat_page.update_model_label(self.config.get("model"))
        self.chat_page.update_wake_word(self.config.get("voice", {}).get("wake_word", "Jarvis"))
        self.chat_page.update_assistant_name(self.config.get("assistant_name", "JARVIS"))
        self.chat_page.set_voice_controller(self.voice_controller)
        self.chat_page.send_requested.connect(self.chat_controller.send)
        self.chat_page.voice_recording_requested.connect(self.wake_word_detector.stop)

        self.wake_word_detector.detected.connect(self._on_wake_word_detected)
        self.wake_word_detector.recognized.connect(self.chat_page.update_wake_word_recognition)
        self.wake_word_detector.status.connect(self._on_wake_word_status)
        self.wake_word_detector.error.connect(self._on_wake_word_error)
        self.voice_controller.listening_changed.connect(self._on_voice_listening_changed)
        self.voice_controller.transcript_ready.connect(self._on_voice_command_finished)
        self.voice_controller.error.connect(self._on_voice_command_error)

        self._on_settings_changed(
            self.config.get("model"),
            self.config.get("assistant_name", "JARVIS"),
        )

        self.setWindowTitle(self.config.get("assistant_name", "JARVIS"))
        self.resize(1100, 750)

    def show_commands_window(self):
        if self.commands_window is None:
            self.commands_window = CommandsWindow(self.chat_service.router, self)
        else:
            self.commands_window.router = self.chat_service.router
            self.commands_window.refresh()
        self.commands_window.show()
        self.commands_window.raise_()
        self.commands_window.activateWindow()

    def _on_settings_changed(self, model, assistant_name):
        self.application.apply_settings()
        self.chat_page.update_model_label(model)
        self.chat_page.update_wake_word(self.config.get("voice", {}).get("wake_word", "Jarvis"))
        self.chat_page.update_assistant_name(assistant_name)
        self.setWindowTitle(assistant_name or "JARVIS")
        self.chat_page.update_wake_word_recognition("")
        self.settings_applied.emit()

    def _on_wake_word_detected(self, wake_word):
        logger.info("wake_word_triggered wake_word=%r", wake_word)
        self.wake_word_detector.stop()
        self.chat_page.voice_status.setText("Голос: 🔴 wake word услышан, говори…")
        QTimer.singleShot(120, self.voice_controller.start)

    def _on_wake_word_status(self, status):
        self.chat_page.voice_status.setText(status)

    def _on_wake_word_error(self, error):
        logger.error(error)
        self.chat_page.voice_status.setText("Голос: ошибка wake word")

    def _on_voice_listening_changed(self, listening):
        if listening:
            self.wake_word_detector.stop()

    def _on_voice_command_finished(self, text):
        QTimer.singleShot(250, self.wake_word_detector.start)

    def _on_voice_command_error(self, error):
        QTimer.singleShot(250, self.wake_word_detector.start)

    def on_generation_finished(self, stats):
        self.stats_service.add(stats)
        self.stats_page.refresh(stats)
        self.chat_page.finish_generation()

    def on_error(self, error):
        self.chat_page.finish_generation()
        QMessageBox.critical(self, "Ошибка", error)

    def minimize_window(self):
        self.showMinimized()

    def maximize_window(self):
        self.showMaximized()

    def restore_window(self):
        self.showNormal()

    def shutdown(self):
        self.application.shutdown()
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event):
        self.application.shutdown()
        super().closeEvent(event)
