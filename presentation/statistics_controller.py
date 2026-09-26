from __future__ import annotations

import psutil
from PySide6.QtCore import QObject, Signal


class StatisticsController(QObject):
    system_status = Signal(object)

    def __init__(self, statistics_service, ollama_controller, task_runner):
        super().__init__()
        self._service = statistics_service
        self._ollama = ollama_controller
        self._tasks = task_runner

    def add(self, stats):
        self._service.add(stats)

    def refresh(self, stats):
        return stats

    def update_system_status(self, model):
        def work():
            try:
                status = self._ollama._manager.get_model_status(model)
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory()
                return {"status": status, "cpu": cpu, "ram_used": ram.used, "ram_total": ram.total, "ram_percent": ram.percent}
            except Exception:
                return {"status": None, "cpu": 0, "ram_used": 0, "ram_total": 0, "ram_percent": 0}
        future = self._tasks.submit(work)
        future.add_done_callback(self._done)
        return future

    def _done(self, future):
        try:
            result = future.result()
        except Exception:
            result = {"status": None, "cpu": 0, "ram_used": 0, "ram_total": 0, "ram_percent": 0}
        self.system_status.emit(result)
