"""Thread-safe TTS counters for logging and future diagnostics UI."""
from __future__ import annotations

import threading
from dataclasses import asdict, dataclass


@dataclass(frozen=True, slots=True)
class TTSMetricsSnapshot:
    requests: int = 0
    successful_syntheses: int = 0
    prepared_audio_hits: int = 0
    cache_hits: int = 0
    fallback_uses: int = 0
    errors: int = 0
    queue_rejections: int = 0
    synthesis_seconds_total: float = 0.0

    def to_dict(self) -> dict[str, int | float]:
        return asdict(self)


class TTSMetrics:
    """In-memory counters; full text/audio payloads are never retained."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values = {name: 0 for name in TTSMetricsSnapshot.__dataclass_fields__}

    def _increment(self, field: str, value: int | float = 1) -> None:
        with self._lock:
            self._values[field] += value

    def record_request(self) -> None:
        self._increment("requests")

    def record_synthesis(self, elapsed_seconds: float, success: bool = True) -> None:
        with self._lock:
            self._values["synthesis_seconds_total"] += max(0.0, float(elapsed_seconds))
            if success:
                self._values["successful_syntheses"] += 1

    def record_prepared_hit(self) -> None:
        self._increment("prepared_audio_hits")

    def record_cache_hit(self) -> None:
        self._increment("cache_hits")

    def record_fallback(self) -> None:
        self._increment("fallback_uses")

    def record_error(self) -> None:
        self._increment("errors")

    def record_queue_rejection(self) -> None:
        self._increment("queue_rejections")

    def snapshot(self) -> TTSMetricsSnapshot:
        with self._lock:
            return TTSMetricsSnapshot(**self._values)
