from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class SettingsController(QObject):
    models_refreshed = Signal(object)
    microphones_refreshed = Signal(object)
    microphone_tested = Signal(object)
    whisper_progress = Signal(str, int, int, float)
    whisper_state_changed = Signal(str, str)
    whisper_finished = Signal(str, bool, str)
    refresh_finished = Signal(object)

    def __init__(self, config, model_service, dependency_controller, task_runner, event_bus, voice_service):
        super().__init__()
        self._config = config
        self._model_service = model_service
        self._dependency = dependency_controller
        self._tasks = task_runner
        self._events = event_bus
        self._voice = voice_service
        self._events.subscribe("dependency.progress", self.whisper_progress.emit)
        self._events.subscribe("dependency.state_changed", self.whisper_state_changed.emit)
        
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

    def get_rofl_settings(self):
        settings = self._config.get("rofl", {})
        return {
            "chance": float(settings.get("chance", 0.12)),
            "demon_chance": float(settings.get("demon_chance", 0.15)),
        }

    def save_rofl_settings(self, chance, demon_chance):
        rofl = self._config.data.setdefault("rofl", {})
        rofl["chance"] = max(0.0, min(1.0, float(chance)))
        rofl["demon_chance"] = max(0.0, min(1.0, float(demon_chance)))
        self._config.save()
        self._events.emit("rofl.settings_changed", dict(rofl))
        return self.get_rofl_settings()

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
        for name, handler in (("dependency.progress", self.whisper_progress.emit), ("dependency.state_changed", self.whisper_state_changed.emit)):
            self._events.unsubscribe(name, handler)
