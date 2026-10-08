from types import SimpleNamespace

from services.chat_service import ChatService


class FakeProvider:
    def __init__(self):
        self.calls = []

    def stream_chat(self, request):
        self.calls.append([dict(message) for message in request.messages])
        if len(self.calls) == 1:
            yield SimpleNamespace(
                done=False,
                text="",
                tool_calls=[{
                    "function": {
                        "name": "search_files",
                        "arguments": {"name": "tool_test.txt"},
                    }
                }],
                raw={"message": {"role": "assistant", "content": ""}},
                stats=None,
            )
            yield SimpleNamespace(
                done=True,
                text="",
                tool_calls=[],
                raw={"message": {"role": "assistant", "content": ""}},
                stats={"eval_count": 1},
            )
            return

        yield SimpleNamespace(
            done=False,
            text="Файл найден.",
            tool_calls=[],
            raw={"message": {"role": "assistant", "content": "Файл найден."}},
            stats=None,
        )
        yield SimpleNamespace(
            done=True,
            text="",
            tool_calls=[],
            raw={"message": {"role": "assistant", "content": "Файл найден."}},
            stats={"eval_count": 2},
        )


def test_chat_service_executes_tool_then_continues(monkeypatch):
    provider = FakeProvider()
    config = {
        "model": "test-model",
        "temperature": 0.7,
        "context_length": 4096,
        "max_tokens": 512,
        "tools": {"search_files": True},
        "router_only_mode": False,
    }
    service = ChatService(provider, config)
    service.router.tools_for_message = lambda _text: {"search_files"}

    tool_result = {"success": True, "matches": ["tool_test.txt"]}
    monkeypatch.setattr(
        "tools.executor.ToolExecutor.execute",
        lambda self, *args, **kwargs: tool_result,
    )

    service.send("Что находится в файле tool_test.txt?")
    future = service._generation_future
    assert future is not None
    stats = future.result(timeout=5)
    service._generation_done(future)

    assert stats == {"eval_count": 2}
    assert len(provider.calls) == 2
    assert provider.calls[1][-1]["role"] == "tool"
    assert "tool_test.txt" in provider.calls[1][-1]["content"]
    service.tasks.shutdown()
