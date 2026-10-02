from services.rofl_service import RoflService


class FakeEventBus:
    def __init__(self):
        self.handlers = {}

    def subscribe(self, event, handler):
        self.handlers.setdefault(event, []).append(handler)

    def unsubscribe(self, event, handler):
        self.handlers[event].remove(handler)

    def emit(self, event, *args):
        for handler in list(self.handlers.get(event, [])):
            handler(*args)


def test_rofl_ignores_failed_and_other_tools():
    bus = FakeEventBus()
    RoflService(bus)
    emitted = []
    bus.subscribe("chat.rofl_response", emitted.append)

    bus.emit("tool.executed", "open_url", {"url": "https://example.com"}, {"success": True})
    bus.emit("tool.executed", "launch_application", {"target": "test"}, {"success": False})

    assert emitted == []


def test_rofl_emits_normal_response(monkeypatch):
    bus = FakeEventBus()
    RoflService(bus)
    emitted = []
    bus.subscribe("chat.rofl_response", emitted.append)

    values = iter([0.0, 1.0])
    monkeypatch.setattr("services.rofl_service.random.random", lambda: next(values))
    monkeypatch.setattr("services.rofl_service.random.choice", lambda seq: seq[0])

    bus.emit(
        "tool.executed",
        "launch_application",
        {"target": "C:\\Apps\\Kirill.exe"},
        {"success": True, "path": "C:\\Apps\\Kirill.exe"},
    )

    assert emitted == ["Готово, Kirill.exe открыта."]


def test_rofl_emits_demon_response(monkeypatch):
    bus = FakeEventBus()
    RoflService(bus)
    emitted = []
    bus.subscribe("chat.rofl_response", emitted.append)

    values = iter([0.0, 0.0])
    monkeypatch.setattr("services.rofl_service.random.random", lambda: next(values))
    monkeypatch.setattr("services.rofl_service.random.choice", lambda seq: seq[0])

    bus.emit("tool.executed", "launch_application", {"target": "Discord"}, {"success": True})

    assert emitted == ["Ритуал завершён. Он уже здесь."]


def test_router_rofl_uses_latin_response(monkeypatch):
    bus = FakeEventBus()
    service = RoflService(bus)
    emitted = []
    bus.subscribe("chat.rofl_response", emitted.append)

    values = iter([0.0, 0.0])
    monkeypatch.setattr("services.rofl_service.random.random", lambda: next(values))
    monkeypatch.setattr("services.rofl_service.random.choice", lambda seq: seq[0])

    service.maybe_router_response("удали файл test.txt", "Готово.", action="delete")

    assert emitted == ["Deletio perfecta est. Iam non est."]


def test_router_rofl_ignores_failed_response(monkeypatch):
    bus = FakeEventBus()
    service = RoflService(bus)
    emitted = []
    bus.subscribe("chat.rofl_response", emitted.append)

    monkeypatch.setattr("services.rofl_service.random.random", lambda: 0.0)

    service.maybe_router_response(
        "закрой Discord",
        "Не удалось закрыть Discord: процесс не найден.",
        action="close",
    )

    assert emitted == []


def test_router_action_prefers_extended_command():
    assert RoflService._router_action("найди приложение Discord") == "find_application"
    assert RoflService._router_action("открой https://example.com") == "open_url"
