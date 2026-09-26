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

    def __init__(self, config, model_service, dependency_controller, task_runner, event_bus):
        super().__init__()
        self._config = config
        self._model_service = model_service
        self._dependency = dependency_controller
        self._tasks = task_runner
        self._events = event_bus
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
        try:
            import sounddevice as sd
            from voice.devices import list_input_devices, _normalize_name
            current = self._config.get("voice", {})
            current_index = current.get("input_device")
            current_name = current.get("input_device_name")
            devices = list_input_devices(list(sd.query_devices()), list(sd.query_hostapis()))
            result = [{"index": None, "name": "Системный микрофон по умолчанию", "hostapi_name": "", "selected": current_index is None and not current_name}]
            normalized = _normalize_name(current_name or "")
            for device in devices:
                index = int(device["index"])
                name = str(device.get("name", f"Микрофон {index}"))
                selected = bool(normalized and _normalize_name(name) == normalized) or (not current_name and current_index == index)
                result.append({"index": index, "name": name, "hostapi_name": str(device.get("hostapi_name", "")), "selected": selected})
            if not any(item["selected"] for item in result):
                result[0]["selected"] = True
            return {"success": True, "devices": result}
        except Exception as exc:
            return {"success": False, "error": str(exc), "devices": []}

    def test_microphone(self, device):
        def work():
            import numpy as np
            import sounddevice as sd
            from voice.devices import find_supported_sample_rate
            voice = self._config.get("voice", {})
            channels = int(voice.get("channels", 1))
            preferred = int(voice.get("sample_rate", 16000))
            rate = find_supported_sample_rate(device=device, channels=channels, preferred=preferred)
            audio = sd.rec(int(rate * 1.5), samplerate=rate, channels=channels, dtype="float32", device=device, blocking=True)
            audio = np.asarray(audio, dtype=np.float32)
            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
            return {"success": True, "rate": rate, "peak": peak, "rms": rms}
        future = self._tasks.submit(work)
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
        return self._config.get("model"), self._config.get("assistant_name", "JARVIS")

    def close(self):
        for name, handler in (("dependency.progress", self.whisper_progress.emit), ("dependency.state_changed", self.whisper_state_changed.emit)):
            self._events.unsubscribe(name, handler)
