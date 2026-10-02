from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from services.update_checker import UpdateCheckError, UpdateChecker
from services.update_service import UpdateService, UpdateServiceError


class SettingsController(QObject):
    models_refreshed = Signal(object)
    microphones_refreshed = Signal(object)
    microphone_tested = Signal(object)
    whisper_progress = Signal(str, int, int, float)
    whisper_state_changed = Signal(str, str)
    whisper_finished = Signal(str, bool, str)
    refresh_finished = Signal(object)
    update_check_finished = Signal(object)
    update_confirmation_requested = Signal(object)

    def __init__(self, config, model_service, dependency_controller, task_runner, event_bus, voice_service, update_checker=None, update_service=None):
        super().__init__()
        self._config = config
        self._model_service = model_service
        self._dependency = dependency_controller
        self._tasks = task_runner
        self._events = event_bus
        self._voice = voice_service
        self._update_checker = update_checker or UpdateChecker()
        self._update_service = update_service or UpdateService()
        self._events.subscribe("dependency.progress", self.whisper_progress.emit)
        self._events.subscribe("dependency.state_changed", self.whisper_state_changed.emit)
        self._events.subscribe("application.update_check_finished", self._background_update_finished)
        
    def _background_update_finished(self, result):
        self._emit_update_result(self._prepare_update_result(result))

    def check_for_update(self):
        future = self._tasks.submit(self._check_for_update)
        future.add_done_callback(self._update_check_done)
        return future

    def _check_for_update(self):
        try:
            info = self._update_checker.check()
            return self._prepare_update_result({"success": True, "info": info})
        except UpdateCheckError as exc:
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            return {"success": False, "error": "Не удалось проверить обновления: " + str(exc)}

    def _prepare_update_result(self, result):
        if not result.get("success") or "info" not in result:
            return result

        info = result["info"]
        if not getattr(info, "update_available", False):
            return result

        try:
            plan = self._update_service.prepare(info)
        except UpdateServiceError as exc:
            return {"success": False, "error": str(exc), "info": info}

        return {**result, "plan": plan}

    def _update_check_done(self, future):
        try:
            result = future.result()
        except Exception as exc:
            result = {"success": False, "error": "Не удалось проверить обновления: " + str(exc)}
        self._emit_update_result(result)

    def _emit_update_result(self, result):
        self.update_check_finished.emit(result)
        if result.get("success") and result.get("plan") is not None:
            self.update_confirmation_requested.emit(result["plan"])

    def get(self, key, default=None):
        return self._config.get(key, default)

    @property
    def ollama_url(self):
        return self._config.ollama_url

    def whisper_status(self, model_name):
        return self._dependency.whisper_status(model_name)

    def refresh_whisper_statuses(self, model_names):
        return {name: self.whisper_status(name) for name in model_names}

    def ensure_whisper_model(self, model_name):
        future = self._tasks.submit(self._dependency.ensure_whisper_model, model_name)
        future.add_done_callback(lambda f: self._emit_finished("whisper", model_name, f))
        return future

    def _emit_finished(self, kind, model_name, future):
        try:
            result = future.result()
            payload = {"success": True, "result": result}
        except Exception as exc:
            payload = {"success": False, "error": str(exc)}
        self.whisper_finished.emit(model_name, payload.get("success", False), payload.get("error", ""))
        self.refresh_finished.emit(payload)

    def refresh(self):
        def work():
            result = self._model_service.get_models()
            microphones = self.list_microphones()
            return {"models": result if isinstance(result, list) else [], "microphones": microphones}
        future = self._tasks.submit(work)
        future.add_done_callback(self._refresh_done)
        return future

    def _refresh_done(self, future):
        try:
            result = future.result()
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
        self.refresh_finished.emit(result)

    def list_microphones(self):
        return self._voice.list_microphones()

    def test_microphone(self, device):
        future = self._tasks.submit(self._voice.test_microphone, device)
        future.add_done_callback(self._microphone_test_done)
        return future

    def _microphone_test_done(self, future):
        try:
            result = future.result()
        except Exception as exc:
            result = {"success": False, "error": str(exc)}
        self.microphone_tested.emit(result)

    def save(self, values):
        self._config.data["assistant_name"] = values["assistant_name"]
        self._config.data["model"] = values["model"]
        self._config.data["temperature"] = values["temperature"]
        self._config.data["context_length"] = values["context_length"]
        self._config.data["max_tokens"] = values["max_tokens"]
        self._config.data["router_only_mode"] = values["router_only_mode"]
        self._config.data["allow_outside_workspace"] = values["allow_outside_workspace"]
        voice = self._config.data.setdefault("voice", {})
        voice.update(values["voice"])
        self._config.data["ollama"]["base_url"] = values["ollama_url"]
        self._config.save()
        self._voice.apply_config(self._config.data)
        return self._config.get("model"), self._config.get("assistant_name", "JARVIS")

    def close(self):
        for name, handler in (
            ("dependency.progress", self.whisper_progress.emit),
            ("dependency.state_changed", self.whisper_state_changed.emit),
            ("application.update_check_finished", self._background_update_finished),
        ):
            self._events.unsubscribe(name, handler)
