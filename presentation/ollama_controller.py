from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class OllamaController(QObject):
    operation_finished = Signal(str, object)
    status_changed = Signal(object)

    def __init__(self, manager, task_runner):
        super().__init__()
        self._manager = manager
        self._tasks = task_runner

    def started_by_jarvis(self):
        return bool(self._manager.started_by_jarvis)

    def run(self, action, model=None):
        def work():
            if action == "status":
                running = self._manager.is_running()
                loaded = self._manager.get_loaded_models() if running else []
                return {"success": True, "running": running, "loaded": loaded}
            if action == "start":
                self._manager.start(); return {"success": True}
            if action == "stop":
                return self._manager.stop_server()
            if action == "load":
                return self._manager.load_model(model)
            if action == "unload":
                return self._manager.unload_model(model)
            return {"success": False, "error": "Неизвестная операция."}
        future = self._tasks.submit(work)
        future.add_done_callback(lambda f: self._done(action, f))
        return future

    def _done(self, action, future):
        try:
            result = future.result()
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
        if action == "status":
            self.status_changed.emit(result)
        self.operation_finished.emit(action, result)

    def close(self):
        pass
