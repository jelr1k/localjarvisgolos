from __future__ import annotations

from concurrent.futures import Future
from unittest.mock import Mock, patch

import pytest
import requests

from core.exceptions import LLMConnectionError, LLMRequestError
from llm.ollama import OllamaProvider
from llm.request import ChatRequest
from llm.response import GenerationStats, StreamChunk
from llm.statistics import calculate_stats, ns_to_s
from services.model_service import ModelService


class FakeResponse:
    def __init__(self, lines=None, json_data=None, status_code=200):
        self._lines = lines or []
        self._json = json_data if json_data is not None else {}
        self.status_code = status_code
        self.headers = {}
        self.text = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._json

    def iter_lines(self, chunk_size=1, decode_unicode=True):
        return iter(self._lines)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_chat_request_and_stream_chunk_dataclasses_have_stable_defaults():
    request = ChatRequest(model="qwen", messages=[{"role": "user", "content": "hi"}])
    chunk = StreamChunk()
    stats = GenerationStats()

    assert request.thinking is False
    assert request.tools == []
    assert chunk.done is False
    assert chunk.tool_calls == []
    assert stats.total_tokens == 0


def test_statistics_calculate_from_ollama_durations():
    final = {
        "model": "qwen",
        "total_duration": 2_000_000_000,
        "load_duration": 500_000_000,
        "prompt_eval_duration": 250_000_000,
        "eval_duration": 1_000_000_000,
        "eval_count": 40,
        "prompt_eval_count": 10,
    }

    result = calculate_stats(final, 0.2, thinking=True)

    assert ns_to_s(1_500_000_000) == 1.5
    assert result["model"] == "qwen"
    assert result["total_tokens"] == 50
    assert result["generation_speed_tps"] == pytest.approx(40.0)
    assert result["ttft_s"] == 0.2
    assert result["thinking"] is True


def test_statistics_handles_missing_durations():
    result = calculate_stats({"model": "qwen"}, None, False)
    assert result["total_time_s"] == 0.0
    assert result["generation_speed_tps"] == 0.0
    assert result["total_tokens"] == 0


def test_model_service_delegates_to_provider():
    provider = Mock()
    provider.list_models.return_value = ["a", "b"]
    service = ModelService(provider)

    assert service.get_models() == ["a", "b"]
    provider.list_models.assert_called_once()


def test_ollama_provider_list_models_builds_expected_url():
    provider = OllamaProvider("http://localhost:11434/")
    response = FakeResponse(json_data={"models": [{"name": "qwen"}, {}, {"name": "llama"}]})

    with patch("llm.ollama.requests.get", return_value=response) as get:
        assert provider.list_models() == ["qwen", "llama"]

    get.assert_called_once_with("http://localhost:11434/api/tags", timeout=5)


def test_ollama_provider_list_models_wraps_connection_error():
    provider = OllamaProvider()

    with patch("llm.ollama.requests.get", side_effect=requests.ConnectionError("offline")):
        with pytest.raises(LLMConnectionError):
            provider.list_models()


def test_ollama_provider_streams_text_thinking_tools_invalid_json_and_stats():
    provider = OllamaProvider("http://localhost:11434")
    request = ChatRequest(
        model="qwen",
        messages=[{"role": "user", "content": "hello"}],
        thinking=True,
        temperature=0.2,
        context_length=4096,
        max_tokens=128,
        tools=[{"type": "function"}],
    )
    lines = [
        "{not-json",
        '{"message":{"content":"Hi"}}',
        '{"message":{"thinking":"reason"}}',
        '{"message":{"tool_calls":[{"function":{"name":"search_files","arguments":{"name":"x"}}}]}}',
        '{"done":true,"model":"qwen","total_duration":2000000000,"load_duration":500000000,"prompt_eval_duration":250000000,"eval_duration":1000000000,"eval_count":10,"prompt_eval_count":5}',
    ]
    response = FakeResponse(lines=lines)

    with patch("llm.ollama.requests.post", return_value=response) as post:
        chunks = list(provider.stream_chat(request))

    assert chunks[-1].done is True
    assert chunks[0].text == "Hi"
    assert chunks[1].thinking == "reason"
    assert chunks[2].tool_calls[0]["function"]["name"] == "search_files"
    assert isinstance(chunks[-1].stats, GenerationStats)
    assert chunks[-1].stats.output_tokens == 10

    payload = post.call_args.kwargs["json"]
    assert payload["think"] is True
    assert payload["options"]["num_ctx"] == 4096
    assert payload["tools"] == request.tools


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (requests.Timeout("slow"), LLMRequestError),
        (requests.ConnectionError("offline"), LLMConnectionError),
        (requests.HTTPError("bad"), LLMRequestError),
    ],
)
def test_ollama_provider_maps_request_errors(exc, expected):
    provider = OllamaProvider()
    request = ChatRequest(model="qwen", messages=[])

    with patch("llm.ollama.requests.post", side_effect=exc):
        with pytest.raises(expected):
            list(provider.stream_chat(request))
