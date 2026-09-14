import json
import logging
import time

import requests

from llm.base import LLMProvider
from llm.response import StreamChunk, GenerationStats
from llm.statistics import calculate_stats
from core.exceptions import LLMConnectionError, LLMRequestError


logger = logging.getLogger("jarvis.llm")


class OllamaProvider(LLMProvider):
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        logger.debug("ollama_provider_created base_url=%s", self.base_url)

    def set_base_url(self, base_url):
        self.base_url = base_url.rstrip("/")
        logger.info("ollama_base_url_changed base_url=%s", self.base_url)

    def _url(self, endpoint):
        return f"{self.base_url}{endpoint}"

    def list_models(self):
        logger.info("ollama_list_models_start")
        try:
            response = requests.get(self._url("/api/tags"), timeout=5)
            logger.debug("ollama_response endpoint=/api/tags status=%s headers=%r", response.status_code, dict(response.headers))
            response.raise_for_status()
            data = response.json()
            models = [model.get("name", "") for model in data.get("models", []) if model.get("name")]
            logger.info("ollama_list_models_finish count=%d models=%r", len(models), models)
            return models
        except requests.RequestException as exc:
            logger.exception("ollama_list_models_failed")
            raise LLMConnectionError(f"Не удалось подключиться к Ollama:\n{exc}") from exc

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
        if request.tools:
            payload["tools"] = request.tools

        started = time.perf_counter()
        first_token_at = None
        chunk_count = 0
        logger.info("ollama_chat_start url=%s payload=%r", self._url("/api/chat"), payload)

        try:
            with requests.post(self._url("/api/chat"), json=payload, stream=True, timeout=(10, 600)) as response:
                logger.info("ollama_chat_connected status=%s headers=%r", response.status_code, dict(response.headers))
                response.raise_for_status()

                for line in response.iter_lines(chunk_size=1, decode_unicode=True):
                    if not line:
                        continue
                    chunk_count += 1
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("ollama_invalid_json_chunk line=%r", line)
                        continue

                    logger.debug("ollama_chunk index=%d data=%r", chunk_count, chunk)
                    message = chunk.get("message") or {}
                    text = message.get("content") or ""
                    thinking = message.get("thinking") or ""
                    tool_calls = message.get("tool_calls") or []

                    if text or thinking or tool_calls:
                        if first_token_at is None:
                            first_token_at = time.perf_counter() - started
                            logger.info("ollama_first_token elapsed=%.4fs", first_token_at)
                        yield StreamChunk(text=text, thinking=thinking, tool_calls=tool_calls, done=False, raw=chunk)

                    if chunk.get("done"):
                        stats_dict = calculate_stats(chunk, first_token_at, request.thinking)
                        logger.info("ollama_chat_done elapsed=%.4fs chunks=%d stats=%r", time.perf_counter() - started, chunk_count, stats_dict)
                        yield StreamChunk(done=True, stats=GenerationStats(**stats_dict), raw=chunk)

        except requests.Timeout as exc:
            logger.exception("ollama_chat_timeout elapsed=%.4fs", time.perf_counter() - started)
            raise LLMRequestError("Ollama слишком долго не отвечает.") from exc
        except requests.ConnectionError as exc:
            logger.exception("ollama_chat_connection_error elapsed=%.4fs", time.perf_counter() - started)
            raise LLMConnectionError("Не удалось подключиться к Ollama.") from exc
        except requests.RequestException as exc:
            logger.exception("ollama_chat_request_error elapsed=%.4fs", time.perf_counter() - started)
            raise LLMRequestError(f"Ошибка запроса к Ollama:\n{exc}") from exc
