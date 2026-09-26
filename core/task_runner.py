from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Any


class TaskRunner:
    """Small backend task runner. No GUI/framework dependency."""

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="jarvis-task",
        )
        self._closed = False

    def submit(self, function: Callable[..., Any], *args, **kwargs) -> Future:
        if self._closed:
            raise RuntimeError("TaskRunner is already shut down")
        return self._executor.submit(function, *args, **kwargs)

    def shutdown(self, wait: bool = False, cancel_futures: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
