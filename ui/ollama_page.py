from __future__ import annotations
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QGroupBox,QHBoxLayout,QLabel,QMessageBox,QPushButton,QVBoxLayout,QWidget

class OllamaPage(QWidget):
    def __init__(self,controller,config):
        super().__init__();self.controller=controller;self.config=config;self.busy=False;self.status_busy=False
        self.server_label=QLabel("Сервер: проверка…");self.model_label=QLabel("Модель: проверка…");self.action_label=QLabel("Готово")
        self.start_button=QPushButton("Запустить Ollama Server");self.stop_button=QPushButton("Остановить Ollama Server");self.refresh_button=QPushButton("Обновить статус");self.load_button=QPushButton("Загрузить модель");self.unload_button=QPushButton("Выгрузить модель")
        self.start_button.clicked.connect(lambda:self._run("start"));self.stop_button.clicked.connect(lambda:self._run("stop"));self.refresh_button.clicked.connect(self.refresh);self.load_button.clicked.connect(lambda:self._run("load",self.config.get("model")));self.unload_button.clicked.connect(lambda:self._run("unload",self.config.get("model")))
        self.controller.operation_finished.connect(self._operation_finished);self.controller.status_changed.connect(self._status_finished)
        box=QGroupBox("Ollama Server");buttons=QHBoxLayout(box);[buttons.addWidget(b) for b in (self.start_button,self.stop_button,self.refresh_button)]
        model_box=QGroupBox("Текущая модель");ml=QHBoxLayout(model_box);ml.addWidget(self.load_button);ml.addWidget(self.unload_button)
        status=QGroupBox("Состояние");sl=QVBoxLayout(status);[sl.addWidget(x) for x in (self.server_label,self.model_label,self.action_label)]
        root=QVBoxLayout(self);root.addWidget(box);root.addWidget(model_box);root.addWidget(status);root.addStretch()
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(2000);self.refresh()
    def _set_busy(self,busy):
        self.busy=busy;enabled=not busy and not self.status_busy
        self.refresh_button.setEnabled(enabled);running=self.server_label.text().endswith("запущен");stopped=self.server_label.text().endswith("остановлен")
        self.start_button.setEnabled(enabled and stopped);self.stop_button.setEnabled(enabled and self.controller.started_by_jarvis() and running);self.load_button.setEnabled(enabled and running);self.unload_button.setEnabled(enabled and running)
    def _run(self,action,model=None):
        if self.busy or self.status_busy:return
        self._set_busy(True);self.action_label.setText("Выполняется…");self.controller.run(action,model)
    def _operation_finished(self,action,result):
        if action=="status":return
        self._set_busy(False)
        if result.get("success"):self.action_label.setText("Операция выполнена")
        else:self.action_label.setText("Ошибка операции");QMessageBox.warning(self,"Ollama",result.get("error","Неизвестная ошибка"))
        self.refresh()
    def refresh(self):
        if self.status_busy or self.busy:return
        self.status_busy=True;self._set_busy(False);self.controller.run("status")
    def _status_finished(self,result):
        self.status_busy=False;running=bool(result.get("running")) if result.get("success") else False
        loaded={item.get("name") or item.get("model") for item in (result.get("loaded") or [])};model=self.config.get("model","—")
        if result.get("success"):
            self.server_label.setText(f"Сервер: {'запущен' if running else 'остановлен'}");self.model_label.setText(f"Модель {model}: {'загружена' if model in loaded else 'не загружена'}")
        else:self.server_label.setText("Сервер: ошибка подключения");self.model_label.setText(f"Модель {model}: неизвестно")
        self._set_busy(self.busy)
