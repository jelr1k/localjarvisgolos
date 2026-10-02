"""Stage 14: launch a separate updater and restart JARVIS safely.

The running JARVIS process must not replace its own files on Windows. This
service starts a separate updater process, passes it the current PID and the
validated update archive, and then lets the updater install the update after
JARVIS has exited.

The updater itself lives in start/updater.py so the mechanism can later be
packaged as JarvisUpdater.exe without changing the update workflow.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
import sys


class UpdateRelaunchError(RuntimeError):
    """Raised when the updater process cannot be started safely."""


@dataclass(frozen=True)
class UpdateRelaunchPlan:
    updater_path: Path
    application_root: Path
    archive_path: Path
    expected_size: int
    process_id: int
    python_executable: Path


class UpdateRelauncher:
    """Prepare and launch the standalone updater process."""

    def __init__(
        self,
        *,
        updater_path: Path | None = None,
        python_executable: Path | None = None,
    ):
        root = Path(__file__).resolve().parents[1]
        self._updater_path = (
            Path(updater_path).resolve()
            if updater_path is not None
            else root / "start" / "updater.py"
        )
        self._python_executable = (
            Path(python_executable).resolve()
            if python_executable is not None
            else Path(sys.executable).resolve()
        )

    def prepare(
        self,
        application_root: Path,
        archive_path: Path,
        expected_size: int,
        *,
        process_id: int | None = None,
    ) -> UpdateRelaunchPlan:
        root = Path(application_root).resolve()
        archive = Path(archive_path).resolve()

        if not root.is_dir():
            raise UpdateRelaunchError("Каталог приложения для перезапуска не найден.")
        if not self._updater_path.is_file():
            raise UpdateRelaunchError("Файл отдельного updater-процесса не найден.")
        if not archive.is_file():
            raise UpdateRelaunchError("Архив обновления для перезапуска не найден.")
        if expected_size <= 0:
            raise UpdateRelaunchError("Размер архива обновления должен быть больше нуля.")
        if not self._python_executable.is_file():
            raise UpdateRelaunchError("Python для запуска updater-процесса не найден.")

        pid = os.getpid() if process_id is None else int(process_id)
        if pid <= 0:
            raise UpdateRelaunchError("Некорректный PID текущего приложения.")

        return UpdateRelaunchPlan(
            updater_path=self._updater_path,
            application_root=root,
            archive_path=archive,
            expected_size=int(expected_size),
            process_id=pid,
            python_executable=self._python_executable,
        )

    @staticmethod
    def command(plan: UpdateRelaunchPlan) -> list[str]:
        return [
            str(plan.python_executable),
            str(plan.updater_path),
            "--pid",
            str(plan.process_id),
            "--root",
            str(plan.application_root),
            "--archive",
            str(plan.archive_path),
            "--expected-size",
            str(plan.expected_size),
        ]

    def launch(self, plan: UpdateRelaunchPlan) -> subprocess.Popen:
        try:
            return subprocess.Popen(
                self.command(plan),
                cwd=str(plan.application_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
        except OSError as exc:
            raise UpdateRelaunchError(
                f"Не удалось запустить отдельный updater-процесс: {exc}"
            ) from exc
