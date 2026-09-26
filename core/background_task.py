from __future__ import annotations

from core.task_runner import TaskRunner


class BackgroundTask:
    """Compatibility wrapper for code that submits a blocking callable."""

    def __init__(self, function):
        self.function = function

    def submit(self, runner: TaskRunner):
        return runner.submit(self.function)
