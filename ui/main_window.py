from __future__ import annotations

import logging
from PySide6.QtCore import QTimer,Signal
from PySide6.QtWidgets import QHBoxLayout,QMessageBox,QPushButton,QTabWidget,QVBoxLayout,QWidget
from ui.alias_page import AliasPage
from ui.chat_page import ChatPage
from ui.commands_window import CommandsWindow
from ui.ollama_page import OllamaPage
from ui.settings_page import SettingsPage
from ui.statistics_page import StatisticsPage
from ui.tools_page import ToolsPage
from ui.workspace_tab import WorkspaceTab

logger=logging.getLogger("jarvis.ui")

class MainWindow(QWidget):
    settings_applied=Signal()
    def __init__(self,application_controller,chat_controller,voice_controller,wake_word_controller,dependency_controller,settings_controller,alias_controller,tools_controller,ollama_controller,statistics_controller,workspace_controller):
        super().__init__()
        self.application_controller=application_controller;self.chat_controller=chat_controller;self.voice_controller=voice_controller;self.wake_word_detector=wake_word_controller
        self.settings_controller=settings_controller;self.alias_controller=alias_controller;self.tools_controller=tools_controller;self.ollama_controller=ollama_controller;self.statistics_controller=statistics_controller
        self.chat_page=ChatPage(self.settings_controller);self.stats_page=StatisticsPage(statistics_controller);self.settings_page=SettingsPage(settings_controller);self.alias_page=AliasPage(alias_controller);self.workspace_page=WorkspaceTab(workspace_controller);self.tools_page=ToolsPage(tools_controller);self.ollama_page=OllamaPage(ollama_controller,settings_controller)
        self.tabs=QTabWidget()
        for page,title in ((self.chat_page,"Чат"),(self.stats_page,"Генерация"),(self.settings_page,"Настройки"),(self.alias_page,"Алиасы"),(self.workspace_page,"Workspace"),(self.tools_page,"Инструменты"),(self.ollama_page,"Ollama")):self.tabs.addTab(page,title)
        self.commands_window=None;self.commands_button=QPushButton("Команды");self.commands_button.clicked.connect(self.show_commands_window)
        top=QHBoxLayout();top.addStretch();top.addWidget(self.commands_button);root=QVBoxLayout(self);root.addLayout(top);root.addWidget(self.tabs)
        self.chat_controller.set_ui_actions({"shutdown":self.shutdown,"minimize":self.minimize_window,"maximize":self.maximize_window,"restore":self.restore_window})
        self.chat_controller.chunk_received.connect(self.chat_page.on_chunk);self.chat_controller.direct_response.connect(self.chat_page.on_direct_response);self.chat_controller.generation_finished.connect(self.on_generation_finished);self.chat_controller.error.connect(self.on_error)
        self.settings_page.settings_changed.connect(self._on_settings_changed);self.tools_page.tools_changed.connect(self.chat_controller.refresh_tools)
        model=self.settings_controller.get("model");name=self.settings_controller.get("assistant_name","JARVIS");wake=self.settings_controller.get("voice",{}).get("wake_word","Jarvis")
        self.chat_page.update_model_label(model);self.chat_page.update_wake_word(wake);self.chat_page.update_assistant_name(name);self.chat_page.set_voice_controller(self.voice_controller);self.chat_page.send_requested.connect(self.chat_controller.send);self.chat_page.voice_recording_requested.connect(self.wake_word_detector.stop)
        self.wake_word_detector.detected.connect(self._on_wake_word_detected);self.wake_word_detector.recognized.connect(self.chat_page.update_wake_word_recognition);self.wake_word_detector.status.connect(self._on_wake_word_status);self.wake_word_detector.error.connect(self._on_wake_word_error)
        self.voice_controller.listening_changed.connect(self._on_voice_listening_changed);self.voice_controller.transcript_ready.connect(self._on_voice_command_finished);self.voice_controller.error.connect(self._on_voice_command_error)
        self.setWindowTitle(name);self.resize(1100,750)

    def show_commands_window(self):
        if self.commands_window is None:self.commands_window=CommandsWindow(self.chat_controller,self)
        else:self.commands_window.refresh()
        self.commands_window.show();self.commands_window.raise_();self.commands_window.activateWindow()

    def _on_settings_changed(self,model,name):
        self.application_controller.apply_settings();self.chat_page.update_model_label(model);self.chat_page.update_wake_word(self.settings_controller.get("voice",{}).get("wake_word","Jarvis"));self.chat_page.update_assistant_name(name);self.setWindowTitle(name or "JARVIS");self.chat_page.update_wake_word_recognition("");self.settings_applied.emit()

    def _on_wake_word_detected(self,wake_word):
        logger.info("wake_word_triggered wake_word=%r",wake_word);self.wake_word_detector.stop();self.chat_page.voice_status.setText("Голос: 🔴 wake word услышан, говори…");QTimer.singleShot(120,self.voice_controller.start)
    def _on_wake_word_status(self,status):self.chat_page.voice_status.setText(status)
    def _on_wake_word_error(self,error):logger.error(error);self.chat_page.voice_status.setText("Голос: ошибка wake word")
    def _on_voice_listening_changed(self,listening):
        if listening:self.wake_word_detector.stop()
    def _on_voice_command_finished(self,text):QTimer.singleShot(250,self.wake_word_detector.start)
    def _on_voice_command_error(self,error):QTimer.singleShot(250,self.wake_word_detector.start)
    def on_generation_finished(self,stats):
        self.statistics_controller.add(stats);self.stats_page.refresh(stats);self.chat_page.finish_generation()
    def on_error(self,error):self.chat_page.finish_generation();QMessageBox.critical(self,"Ошибка",error)
    def minimize_window(self):self.showMinimized()
    def maximize_window(self):self.showMaximized()
    def restore_window(self):self.showNormal()
    def shutdown(self):self.application_controller.shutdown()
    def closeEvent(self,event):self.application_controller.shutdown();super().closeEvent(event)
