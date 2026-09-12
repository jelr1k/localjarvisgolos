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
            if self.action == "start":
                result = self._safe_start()
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

    def _safe_start(self):
        try:
            self.manager.start()
            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class OllamaPage(QWidget):
    def __init__(self, config, ollama_manager):
        super().__init__()
        self.config = config
        self.manager = ollama_manager
        self.pool = QThreadPool(self)
        self.busy = False

        self.server_label = QLabel()
        self.model_label = QLabel()
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
        for button in (self.start_button, self.stop_button, self.refresh_button, self.load_button, self.unload_button):
            button.setEnabled(not busy)

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
        running = self.manager.is_running()
        loaded = self.manager.get_loaded_models() if running else []
        model = self.config.get("model", "—")
        loaded_names = {item.get("name") or item.get("model") for item in loaded}

        self.server_label.setText(f"Сервер: {'запущен' if running else 'остановлен'}")
        self.model_label.setText(
            f"Модель {model}: {'загружена' if model in loaded_names else 'не загружена'}"
        )
        self.start_button.setEnabled(not self.busy and not running)
        self.stop_button.setEnabled(not self.busy and running and self.manager.started_by_jarvis)
        self.refresh_button.setEnabled(not self.busy)
        self.load_button.setEnabled(not self.busy and running)
        self.unload_button.setEnabled(not self.busy and running and model in loaded_names)
