from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

from core import logging_config
from core.ollama_manager import OllamaManager
from core.workspace_view_model import WorkspaceViewModel


def _close_logger(name: str) -> None:
    logger = logging.getLogger(name)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def test_configured_handler_writes_to_requested_file(tmp_path):
    path = tmp_path / "nested" / "commands.log"
    path.parent.mkdir()
    handler = logging_config._handler(path, logging.INFO)
    logger = logging.getLogger("test.handler")
    logger.handlers.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)

    try:
        logger.info("hello")
        handler.flush()
        assert "hello" in path.read_text(encoding="utf-8")
        assert handler.level == logging.INFO
        assert isinstance(handler.formatter, logging.Formatter)
    finally:
        _close_logger("test.handler")


def test_configure_logger_adds_debug_and_error_handlers(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path)
    logger_name = "jarvis.test_layer_logger"
    _close_logger(logger_name)

    logger = logging_config._configure_logger(logger_name, "test.log")
    try:
        assert logger.level == logging.DEBUG
        assert logger.propagate is False
        assert len(logger.handlers) == 2
        assert {handler.level for handler in logger.handlers} == {logging.DEBUG, logging.ERROR}
    finally:
        _close_logger(logger_name)


def test_log_event_emits_compact_json_payload(monkeypatch):
    sink = Mock()
    monkeypatch.setattr(logging_config.logging, "getLogger", lambda _name: sink)

    logging_config.log_event("demo", value=123, text="привет")

    payload = json.loads(sink.info.call_args.args[0])
    assert payload == {"event": "demo", "value": 123, "text": "привет"}


def test_log_event_falls_back_when_json_serialization_fails(monkeypatch):
    sink = Mock()
    monkeypatch.setattr(logging_config.logging, "getLogger", lambda _name: sink)
    dumps = Mock(side_effect=[TypeError("boom"), '{"event":"fallback","serialization_error":true}'])
    monkeypatch.setattr(logging_config.json, "dumps", dumps)

    logging_config.log_event("fallback", value=object())

    assert dumps.call_count == 2
    assert json.loads(sink.info.call_args.args[0])["serialization_error"] is True


def test_workspace_view_model_refresh_collects_automatic_and_user_aliases(tmp_path):
    folder = tmp_path / "docs"
    folder.mkdir()
    file = folder / "readme.txt"
    file.write_text("hello", encoding="utf-8")

    aliases = Mock()
    aliases.automatic_aliases.side_effect = lambda category, name: [f"auto:{name}"]
    aliases.get_aliases.side_effect = lambda category, name: [f"user:{name}"]

    model = WorkspaceViewModel(tmp_path, aliases)
    objects = model.refresh()

    readme = next(item for item in objects if item.entry.name == "readme.txt")
    assert readme.automatic_aliases == ("auto:readme.txt",)
    assert "user:readme.txt" in readme.user_aliases
    assert aliases.ensure_automatic_aliases.called


def test_workspace_view_model_set_and_remove_aliases_delegate(tmp_path):
    file = tmp_path / "test.txt"
    file.write_text("x", encoding="utf-8")
    aliases = Mock()
    model = WorkspaceViewModel(tmp_path, aliases)
    entry = next(item for item in model.index.entries() if item.name == "test.txt")

    model.set_aliases(entry, ["one", "two"])
    model.remove_object_aliases(entry)

    aliases.set_aliases.assert_called_once_with("files", "test.txt", ["one", "two"])
    aliases.remove_object.assert_called_once_with("files", "test.txt")


def test_workspace_view_model_add_file_refreshes_index_and_aliases(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    workspace_file = tmp_path / "copied.txt"
    aliases = Mock()

    def add_file(_source):
        workspace_file.write_text("hello", encoding="utf-8")
        return workspace_file

    with patch("tools.paths.add_file_to_workspace", side_effect=add_file):
        model = WorkspaceViewModel(tmp_path, aliases)
        result = model.add_file(source)

    assert result == workspace_file
    aliases.ensure_automatic_aliases.assert_called_with("files", "copied.txt")


def test_ollama_manager_get_models_and_loaded_models_return_empty_on_api_errors():
    manager = OllamaManager()
    with patch.object(manager, "is_running", return_value=True),          patch("core.ollama_manager.requests.get", side_effect=ValueError("bad json")):
        assert manager.get_models() == []
        assert manager.get_loaded_models() == []


def test_ollama_manager_start_success_after_server_becomes_ready():
    manager = OllamaManager()
    process = Mock()
    process.pid = 123
    process.poll.return_value = None

    with patch.object(manager, "is_running", side_effect=[False, True]),          patch("core.ollama_manager.subprocess.Popen", return_value=process) as popen,          patch("core.ollama_manager.time.sleep"):
        assert manager.start(timeout=2) is True

    popen.assert_called_once()
    assert manager.process is process
    assert manager.started_by_jarvis is True


def test_ollama_manager_start_raises_when_child_exits_early():
    manager = OllamaManager()
    process = Mock()
    process.pid = 123
    process.poll.return_value = 1

    with patch.object(manager, "is_running", return_value=False),          patch("core.ollama_manager.subprocess.Popen", return_value=process):
        try:
            manager.start(timeout=2)
        except RuntimeError as exc:
            assert "завершилась сразу" in str(exc)
        else:
            raise AssertionError("expected RuntimeError")


def test_ollama_manager_stop_server_terminates_processes_and_clears_state():
    manager = OllamaManager()
    manager.started_by_jarvis = True
    manager.process = Mock(pid=55, poll=Mock(return_value=None))
    server = Mock(pid=55)

    with patch.object(manager, "_server_processes", return_value=[server]),          patch("core.ollama_manager.psutil.wait_procs", side_effect=[([], []),]),          patch.object(manager, "is_running", return_value=False):
        result = manager.stop_server()

    server.terminate.assert_called_once()
    assert result["success"] is True
    assert manager.process is None
    assert manager.started_by_jarvis is False
