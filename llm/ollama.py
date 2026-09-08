import json
import time

import requests

from llm.base import LLMProvider
from llm.response import StreamChunk, GenerationStats
from llm.statistics import calculate_stats
from core.exceptions import LLMConnectionError, LLMRequestError


class OllamaProvider(LLMProvider):
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def set_base_url(self, base_url):
        self.base_url = base_url.rstrip("/")

    def _url(self, endpoint):
        return f"{self.base_url}{endpoint}"

    def list_models(self):
        try:
            response = requests.get(
                self._url("/api/tags"),
                timeout=5
            )
            response.raise_for_status()

            return [
                model.get("name", "")
                for model in response.json().get("models", [])
                if model.get("name")
            ]

        except requests.RequestException as exc:
            raise LLMConnectionError(
                f"Не удалось подключиться к Ollama:\n{exc}"
            ) from exc

    def stream_chat(self, request):
        payload = {
            "model": request.model,
            "messages": request.messages,
            "stream": True,
            "think": request.thinking,
            "options": {
                "temperature": request.temperature,
                "num_ctx": request.context_length,
                "num_predict": request.max_tokens,
            },
        }

        started = time.perf_counter()
        first_token_at = None

        try:
            with requests.post(
                self._url("/api/chat"),
                json=payload,
                stream=True,
                timeout=(10, 600),
            ) as response:

                response.raise_for_status()

                for line in response.iter_lines(
                    chunk_size=1,
                    decode_unicode=True
                ):
                    if not line:
                        continue

                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    message = chunk.get("message") or {}

                    text = message.get("content") or ""
                    thinking = message.get("thinking") or ""

                    if text or thinking:
                        if first_token_at is None:
                            first_token_at = (
                                time.perf_counter() - started
                            )

                        yield StreamChunk(
                            text=text,
                            thinking=thinking,
                            done=False,
                            raw=chunk,
                        )

                    if chunk.get("done"):
                        stats_dict = calculate_stats(
                            chunk,
                            first_token_at,
                            request.thinking,
                        )

                        stats = GenerationStats(**stats_dict)

                        yield StreamChunk(
                            done=True,
                            stats=stats,
                            raw=chunk,
                        )

        except requests.Timeout as exc:
            raise LLMRequestError(
                "Ollama слишком долго не отвечает."
            ) from exc

        except requests.ConnectionError as exc:
            raise LLMConnectionError(
                "Не удалось подключиться к Ollama."
            ) from exc

        except requests.RequestException as exc:
            raise LLMRequestError(
                f"Ошибка запроса к Ollama:\n{exc}"
            ) from exc
