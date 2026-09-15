from types import SimpleNamespace

from services.chat_service import GenerationWorker


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


def test_generation_worker_executes_tool_then_continues(monkeypatch):
    provider = FakeProvider()
    request = SimpleNamespace(
        model="test-model",
        messages=[{"role": "user", "content": "Найди файл tool_test.txt"}],
        thinking=False,
        temperature=0.7,
        context_length=4096,
        max_tokens=512,
        tools=[{"function": {"name": "search_files"}}],
    )
    config = {"tools": {"search_files": True}}
    worker = GenerationWorker(provider, request, config, alias_manager=None)
    tool_result = {"success": True, "matches": ["tool_test.txt"]}
    monkeypatch.setattr(worker.executor, "execute", lambda *args, **kwargs: tool_result)

    finished = []
    failed = []
    worker.finished.connect(lambda stats: finished.append(stats))
    worker.failed.connect(lambda error: failed.append(error))

    worker.run()

    assert not failed
    assert finished == [{"eval_count": 2}]
    assert len(provider.calls) == 2
    assert provider.calls[1][-1]["role"] == "tool"
    assert "tool_test.txt" in provider.calls[1][-1]["content"]
