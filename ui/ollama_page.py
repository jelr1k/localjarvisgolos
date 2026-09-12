from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, QTimer
from PySide6.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget


class _OllamaWorkerSignals(QObject):
    finished = Signal(object)


class _OllamaWorker(QRunnable):
    def __init__(self, action, manager, model=None):
        super().__init__()
        self.action = action
        self.manager = manager
        self.model = model
        self.signals = _OllamaWorkerSignals()

    def run(self):
        try:
            if self.action == "status":
                running = self.manager.is_running()
                loaded = self.manager.get_loaded_models() if running else []
                result = {"success": True, "running": running, "loaded": loaded}
            elif self.action == "start":
                self.manager.start()
                result = {"success": True}
            elif self.action == "stop":
                result = self.manager.stop_server()
            elif self.action == "load":
                result = self.manager.load_model(self.model)
            elif self.action == "unload":
                result = self.manager.unload_model(self.model)
            else:
                result = {"success": False, "error": "Неизвестная операция."}
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
        self.signals.finished.emit(result)


class OllamaPage(QWidget):
    def __init__(self, config, ollama_manager):
        super().__init__()
        self.config = config
        self.manager = ollama_manager
        self.pool = QThreadPool(self)
        self.busy = False
        self.status_busy = False

        self.server_label = QLabel("Сервер: проверка…")
        self.model_label = QLabel("Модель: проверка…")
        self.action_label = QLabel("Готово")

        self.start_button = QPushButton("Запустить Ollama Server")
        self.stop_button = QPushButton("Остановить Ollama Server")
        self.refresh_button = QPushButton("Обновить статус")
        self.load_button = QPushButton("Загрузить модель")
        self.unload_button = QPushButton("Выгрузить модель")

        self.start_button.clicked.connect(lambda: self._run("start"))
        self.stop_button.clicked.connect(lambda: self._run("stop"))
        self.refresh_button.clicked.connect(self.refresh)
        self.load_button.clicked.connect(lambda: self._run("load", self.config.get("model")))
        self.unload_button.clicked.connect(lambda: self._run("unload", self.config.get("model")))

        box = QGroupBox("Ollama Server")
        buttons = QHBoxLayout(box)
        for button in (self.start_button, self.stop_button, self.refresh_button):
            buttons.addWidget(button)

        model_box = QGroupBox("Текущая модель")
        model_layout = QHBoxLayout(model_box)
        model_layout.addWidget(self.load_button)
        model_layout.addWidget(self.unload_button)

        status = QGroupBox("Состояние")
        status_layout = QVBoxLayout(status)
        status_layout.addWidget(self.server_label)
        status_layout.addWidget(self.model_label)
        status_layout.addWidget(self.action_label)

        layout = QVBoxLayout(self)
        layout.addWidget(box)
        layout.addWidget(model_box)
        layout.addWidget(status)
        layout.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(2000)
        self.refresh()

    def _set_busy(self, busy: bool):
        self.busy = busy
        self.refresh_button.setEnabled(not busy and not self.status_busy)
        self.start_button.setEnabled(not busy and not self.status_busy and self.server_label.text().endswith("остановлен"))
        self.stop_button.setEnabled(not busy and not self.status_busy and self.manager.started_by_jarvis and self.server_label.text().endswith("запущен"))
        self.load_button.setEnabled(not busy and not self.status_busy and self.server_label.text().endswith("запущен"))

    def _run(self, action, model=None):
        if self.busy:
            return
        self._set_busy(True)
        self.action_label.setText("Выполняется…")
        worker = _OllamaWorker(action, self.manager, model)
        worker.signals.finished.connect(self._finished)
        self.pool.start(worker)

    def _finished(self, result):
        self._set_busy(False)
        if result.get("success"):
            self.action_label.setText("Операция выполнена")
        else:
            self.action_label.setText("Ошибка операции")
            QMessageBox.warning(self, "Ollama", result.get("error", "Неизвестная ошибка"))
        self.refresh()

    def refresh(self):
        if self.status_busy or self.busy:
            return
        self.status_busy = True
        self.refresh_button.setEnabled(False)
        worker = _OllamaWorker("status", self.manager)
        worker.signals.finished.connect(self._status_finished)
        self.pool.start(worker)

    def _status_finished(self, result):
        self.status_busy = False
        running = bool(result.get("running")) if result.get("success") else False
        loaded_names = {
            item.get("name") or item.get("model")
            for item in (result.get("loaded") or [])
        }
        model = self.config.get("model", "—")
        if result.get("success"):
            self.server_label.setText(f"Сервер: {'запущен' if running else 'остановлен'}")
            self.model_label.setText(f"Модель {model}: {'загружена' if model in loaded_names else 'не загружена'}")
        else:
            self.server_label.setText("Сервер: ошибка подключения")
            self.model_label.setText(f"Модель {model}: неизвестно")
        self._set_busy(self.busy)
