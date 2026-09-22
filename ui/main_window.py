from __future__ import annotations

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
from voice import VoiceController, WakeWordDetector


class MainWindow(QWidget):
    settings_applied = Signal()

    def __init__(self, chat_service, config, ollama_manager, alias_manager: AliasManager | None = None):
        super().__init__()
        self.chat_service = chat_service
        self.config = config
        self.ollama_manager = ollama_manager
        self.alias_manager = alias_manager or AliasManager()
        self.model_service = ModelService(chat_service.provider)
        self.stats_service = StatisticsService()
        self.voice_controller = VoiceController(config)
        self.wake_word_detector = WakeWordDetector(config)

        self.tabs = QTabWidget()
        self.chat_page = ChatPage(chat_service, config)
        self.stats_page = StatisticsPage(self.stats_service, self.ollama_manager)
        self.settings_page = SettingsPage(config, self.model_service)
        self.alias_page = AliasPage(self.alias_manager)
        self.workspace_page = WorkspaceTab(WORKSPACE_DIR, self.alias_manager)
        self.tools_page = ToolsPage(config)
        self.ollama_page = OllamaPage(config, ollama_manager)
        self.commands_window = None
        self.commands_button = QPushButton("Команды")
        self.commands_button.clicked.connect(self.show_commands_window)

        self.tabs.addTab(self.chat_page, "Чат")
        self.tabs.addTab(self.stats_page, "Генерация")
        self.tabs.addTab(self.settings_page, "Настройки")
        self.tabs.addTab(self.alias_page, "Алиасы")
        self.tabs.addTab(self.workspace_page, "Workspace")
        self.tabs.addTab(self.tools_page, "Инструменты")
        self.tabs.addTab(self.ollama_page, "Ollama")

        top_bar = QHBoxLayout()
        top_bar.addStretch()
        top_bar.addWidget(self.commands_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top_bar)
        layout.addWidget(self.tabs)

        self.chat_service.set_ui_controller(self)

        self.chat_service.chunk_received.connect(self.chat_page.on_chunk)
        self.chat_service.direct_response.connect(self.chat_page.on_direct_response)
        self.chat_service.generation_finished.connect(self.on_generation_finished)
        self.chat_service.error.connect(self.on_error)
        self.settings_page.settings_changed.connect(self._on_settings_changed)
        self.tools_page.tools_changed.connect(self.chat_service.refresh_tools)

        self.chat_page.update_model_label(self.config.get("model"))
        self.chat_page.update_wake_word(self.config.get("voice", {}).get("wake_word", "Jarvis"))
        self.chat_page.update_assistant_name(self.config.get("assistant_name", "JARVIS"))
        self.chat_page.set_voice_controller(self.voice_controller)
        self.chat_page.send_requested.connect(self.chat_service.send)
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

    def show_commands_window(self) -> None:
        if self.commands_window is None:
            self.commands_window = CommandsWindow(self.chat_service.router, self)
        else:
            self.commands_window.router = self.chat_service.router
            self.commands_window.refresh()

        self.commands_window.show()
        self.commands_window.raise_()
        self.commands_window.activateWindow()

    def _on_settings_changed(self, model, assistant_name):
        self.chat_service.provider.set_base_url(self.config.ollama_url)
        self.ollama_manager.set_base_url(self.config.ollama_url)
        self.chat_page.update_model_label(model)
        self.chat_page.update_wake_word(self.config.get("voice", {}).get("wake_word", "Jarvis"))
        self.chat_page.update_assistant_name(assistant_name)
        self.voice_controller.apply_config(self.config)
        window = self.window()
        if window:
            window.setWindowTitle(assistant_name or "JARVIS")
        self.chat_page.update_wake_word_recognition("")
        self.wake_word_detector.apply_config(self.config)
        if self.config.get("voice", {}).get("wake_word_enabled", True):
            self.wake_word_detector.restart()
        else:
            self.wake_word_detector.stop()
        self.settings_applied.emit()

    def _on_wake_word_detected(self, wake_word):
        import logging
        logging.getLogger("jarvis.voice").info("wake_word_triggered wake_word=%r", wake_word)
        self.wake_word_detector.stop()
        self.chat_page.voice_status.setText("Голос: 🔴 wake word услышан, говори…")
        QTimer.singleShot(120, self.voice_controller.start)

    def _on_wake_word_status(self, status):
        self.chat_page.voice_status.setText(status)

    def _on_wake_word_error(self, error):
        import logging
        logging.getLogger("jarvis.voice").error(error)
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

    def minimize_window(self) -> None:
        """Сворачивает именно верхнее окно Jarvis, а не центральный виджет."""
        window = self.window()
        if window is not None:
            window.showMinimized()

    def maximize_window(self) -> None:
        """Разворачивает именно верхнее окно Jarvis."""
        window = self.window()
        if window is not None:
            window.showMaximized()

    def restore_window(self) -> None:
        """Возвращает верхнее окно Jarvis к обычному размеру."""
        window = self.window()
        if window is not None:
            window.showNormal()

    def shutdown(self) -> None:
        """Запрашивает полное завершение верхнего окна Jarvis."""
        window = self.window()
        shutdown = getattr(window, "shutdown", None) if window is not None else None
        if callable(shutdown):
            shutdown()
        elif window is not None:
            window.close()
        else:
            self.close()

    def closeEvent(self, event):
        self.wake_word_detector.close()
        self.voice_controller.close()
        super().closeEvent(event)
