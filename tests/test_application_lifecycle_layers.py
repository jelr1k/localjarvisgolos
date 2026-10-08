from __future__ import annotations

from unittest.mock import Mock, patch

from core.application import JarvisApplication


class FakeFuture:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.callbacks = []

    def add_done_callback(self, callback):
        self.callbacks.append(callback)
        callback(self)

    def exception(self):
        return self._error

    def result(self):
        if self._error:
            raise self._error
        return self._result


class FakeTasks:
    def __init__(self):
        self.submitted = []
        self.shutdown_called = False

    def submit(self, function, *args, **kwargs):
        result = function(*args, **kwargs)
        future = FakeFuture(result=result)
        self.submitted.append((function, args, kwargs))
        return future

    def shutdown(self, **kwargs):
        self.shutdown_called = True


class FakeConfig:
    def __init__(self):
        self.data = {
            "model": "qwen",
            "assistant_name": "JARVIS",
            "voice": {"wake_word_enabled": True},
            "ollama": {"base_url": "http://localhost:11434"},
        }

    def get(self, key, default=None):
        return self.data.get(key, default)

    @property
    def ollama_url(self):
        return self.data["ollama"]["base_url"]


def make_application():
    tasks = FakeTasks()
    config = FakeConfig()
    manager = Mock()
    provider = Mock()
    dependency = Mock()
    permissions = Mock()
    chat = Mock()
    voice = Mock()
    wake = Mock()
    rofl = Mock()
    updater = Mock()
    update_service = Mock()

    patches = [
        patch("core.application.ensure_application_dirs"),
        patch("core.application.prepare_tool_workspace"),
        patch("core.application.TaskRunner", return_value=tasks),
        patch("core.application.ConfigManager", return_value=config),
        patch("core.application.RoflService", return_value=rofl),
        patch("core.application.OllamaManager", return_value=manager),
        patch("core.application.OllamaProvider", return_value=provider),
        patch("core.application.get_dependency_manager", return_value=dependency),
        patch("core.application.PermissionManager", return_value=permissions),
        patch("core.application.ChatService", return_value=chat),
        patch("core.application.VoiceService", return_value=voice),
        patch("core.application.WakeWordDetector", return_value=wake),
        patch("core.application.UpdateChecker", return_value=updater),
        patch("core.application.UpdateService", return_value=update_service),
        patch("core.application.UpdateMonitor", return_value=Mock()),
        patch("core.application.AliasManager", return_value=Mock()),
    ]

    for item in patches:
        item.start()
    try:
        app = JarvisApplication()
    finally:
        for item in reversed(patches):
            item.stop()

    app._test_tasks = tasks
    app._test_config = config
    app._test_manager = manager
    app._test_provider = provider
    app._test_chat = chat
    app._test_voice = voice
    app._test_wake = wake
    app._test_rofl = rofl
    app._test_monitor = app.update_monitor
    return app


def test_application_initializes_backend_without_starting_external_services():
    app = make_application()

    assert app.config.get("model") == "qwen"
    app.ollama_manager.register_model.assert_called_once_with("qwen")
    assert app._started is False
    assert app._shutdown_started is False

    app.shutdown()


def test_application_start_is_idempotent_and_starts_wake_word_and_monitor():
    app = make_application()
    app.start()

    assert app._started is True
    app._test_wake.start.assert_called_once()
    app._test_monitor.start.assert_called_once()
    assert len(app._test_tasks.submitted) == 1

    app.start()
    assert app._test_wake.start.call_count == 1
    assert app._test_monitor.start.call_count == 1

    app.shutdown()


def test_application_apply_settings_updates_backend_and_emits_event():
    app = make_application()
    events = []
    app.events.subscribe("application.settings_applied", lambda *args: events.append(args))

    app.apply_settings()

    app._test_provider.set_base_url.assert_called_once_with("http://localhost:11434")
    app._test_manager.set_base_url.assert_called_once_with("http://localhost:11434")
    app._test_voice.apply_config.assert_called_once_with(app.config)
    app._test_wake.apply_config.assert_called_once_with(app.config)
    app._test_manager.register_model.assert_called_with("qwen")
    assert events == [("qwen", "JARVIS")]

    app.shutdown()


def test_application_shutdown_calls_owned_services_once():
    app = make_application()

    app.shutdown()
    app.shutdown()

    app._test_rofl.close.assert_called_once()
    app._test_monitor.stop.assert_called_once()
    app._test_wake.close.assert_called_once()
    app._test_voice.close.assert_called_once()
    app._test_chat.shutdown.assert_called_once()
    app._test_manager.shutdown_for_app.assert_called_once()
    assert app._test_tasks.shutdown_called is True
