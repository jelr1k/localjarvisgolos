from __future__ import annotations

from unittest.mock import patch
import requests
import pytest

from core.ollama_manager import OllamaManager


class FakeResponse:
    def __init__(self, json_data=None, status_code=200):
        self._json = json_data or {}
        self.status_code = status_code
        self.ok = status_code < 400
        self.headers = {}
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._json


def test_set_base_url_and_register_model():
    manager = OllamaManager("http://localhost:11434/")
    manager.set_base_url("http://example.test/")
    manager.register_model("qwen")
    manager.register_model("")

    assert manager.base_url == "http://example.test"
    assert manager.used_models == {"qwen"}


def test_is_running_and_server_status_handle_success_and_failure():
    manager = OllamaManager()

    with patch("core.ollama_manager.requests.get", return_value=FakeResponse()):
        assert manager.is_running() is True
        assert manager.server_status() == "запущен"

    with patch("core.ollama_manager.requests.get", side_effect=requests.ConnectionError("offline")):
        assert manager.is_running() is False
        assert manager.server_status() == "остановлен"


def test_get_models_and_loaded_models_parse_api_payloads():
    manager = OllamaManager()
    responses = [
        FakeResponse({"models": [{"name": "qwen"}, {"name": ""}]}),
        FakeResponse({"models": [{"name": "qwen", "size": 1}]}),
    ]

    with patch.object(manager, "is_running", return_value=True),          patch("core.ollama_manager.requests.get", side_effect=responses):
        assert manager.get_models() == ["qwen"]
        assert manager.get_loaded_models() == [{"name": "qwen", "size": 1}]


def test_model_status_matches_name_or_model_key():
    manager = OllamaManager()

    with patch.object(manager, "is_running", return_value=True),          patch.object(manager, "get_loaded_models", return_value=[{"model": "qwen:latest"}]):
        assert manager.get_model_status("qwen:latest") == {"model": "qwen:latest"}
        assert manager.get_model_status("") is None


def test_load_model_rejects_missing_model_or_stopped_server():
    manager = OllamaManager()
    assert manager.load_model("")["success"] is False

    with patch.object(manager, "is_running", return_value=False):
        result = manager.load_model("qwen")
    assert result["success"] is False
    assert "не запущен" in result["error"]


def test_load_model_registers_and_reports_status():
    manager = OllamaManager()

    with patch.object(manager, "is_running", return_value=True),          patch("core.ollama_manager.requests.post", return_value=FakeResponse()),          patch.object(manager, "get_model_status", return_value={"name": "qwen"}):
        result = manager.load_model("qwen")

    assert result == {"success": True, "model": "qwen", "status": True}
    assert "qwen" in manager.used_models


def test_unload_model_waits_until_model_disappears():
    manager = OllamaManager()
    manager.used_models.add("qwen")
    status = iter([{"name": "qwen"}, None])

    with patch.object(manager, "is_running", return_value=True),          patch("core.ollama_manager.requests.post", return_value=FakeResponse()),          patch.object(manager, "get_model_status", side_effect=lambda _model: next(status)),          patch("core.ollama_manager.time.sleep"):
        result = manager.unload_model("qwen")

    assert result["success"] is True
    assert result["model"] == "qwen"
    assert "qwen" not in manager.used_models


def test_unload_model_reports_stuck_model_without_real_wait():
    manager = OllamaManager()

    with patch.object(manager, "is_running", return_value=True),          patch("core.ollama_manager.requests.post", return_value=FakeResponse()),          patch.object(manager, "get_model_status", return_value={"name": "qwen"}),          patch("core.ollama_manager.time.monotonic", side_effect=[0.0, 11.0]):
        result = manager.unload_model("qwen")

    assert result["success"] is False
    assert "всё ещё загружена" in result["error"]


def test_unload_models_calls_each_registered_model():
    manager = OllamaManager()
    manager.used_models.update({"a", "b"})

    with patch.object(manager, "unload_model", side_effect=lambda model: {"success": True, "model": model}) as unload:
        result = manager.unload_models()

    assert {item["model"] for item in result} == {"a", "b"}
    assert manager.used_models == set()
    assert unload.call_count == 2


def test_start_skips_process_creation_when_already_running():
    manager = OllamaManager()

    with patch.object(manager, "is_running", return_value=True), patch("core.ollama_manager.subprocess.Popen") as popen:
        assert manager.start() is True
    popen.assert_not_called()
    assert manager.started_by_jarvis is False


def test_start_raises_friendly_error_when_ollama_missing():
    manager = OllamaManager()
    with patch.object(manager, "is_running", return_value=False),          patch("core.ollama_manager.subprocess.Popen", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="найти Ollama"):
            manager.start(timeout=0)


def test_stop_server_reports_missing_process():
    manager = OllamaManager()
    with patch.object(manager, "_server_processes", return_value=[]),          patch.object(manager, "is_running", return_value=False):
        result = manager.stop_server()

    assert result["success"] is False
    assert "Процесс Ollama" in result["error"]


def test_shutdown_for_app_unloads_registered_models():
    manager = OllamaManager()
    with patch.object(manager, "unload_models") as unload:
        manager.shutdown_for_app()
    unload.assert_called_once()
