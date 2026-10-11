from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.update_health import UPDATE_HEALTH_ENV
from services.update_install_policy import UpdateInstallPolicy
from services.update_installer import UpdateInstallError, UpdateInstaller
from services.update_rollback import UpdateRollbackError, UpdateRollbackService


POLL_INTERVAL_SECONDS = 0.5
WAIT_TIMEOUT_SECONDS = 300.0
STARTUP_TIMEOUT_SECONDS = 75.0
_STARTUP_POLL_INTERVAL_SECONDS = 0.25
_DOWNLOAD_DIRECTORY_PREFIX = "jarvis-update-"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JARVIS standalone updater")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--expected-size", type=int, required=True)
    parser.add_argument("--expected-version", default="")
    return parser.parse_args()


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False

    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    output = result.stdout.strip()
    return bool(output) and str(pid) in output


def _wait_for_process_exit(pid: int, timeout: float = WAIT_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    while _is_process_running(pid):
        if time.monotonic() >= deadline:
            raise TimeoutError("JARVIS не завершился за отведённое время.")
        time.sleep(POLL_INTERVAL_SECONDS)


def _restart(application_root: Path, health_file: Path | None = None) -> subprocess.Popen:
    bootstrap = application_root / "start" / "bootstrap.py"
    if not bootstrap.is_file():
        raise FileNotFoundError(f"Bootstrap JARVIS не найден: {bootstrap}")

    if health_file is None:
        health_file = Path(tempfile.gettempdir()) / f"jarvis-startup-health-{os.getpid()}.json"

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    environment = os.environ.copy()
    environment[UPDATE_HEALTH_ENV] = str(health_file)
    return subprocess.Popen(
        [sys.executable, str(bootstrap)],
        cwd=str(application_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
        env=environment,
    )


def _wait_for_startup(
    process: subprocess.Popen,
    health_file: Path,
    *,
    timeout: float = STARTUP_TIMEOUT_SECONDS,
    poll_interval: float = _STARTUP_POLL_INTERVAL_SECONDS,
    expected_version: str | None = None,
) -> dict:
    """Wait until the newly started app confirms its UI/backend are ready."""
    deadline = time.monotonic() + max(0.1, timeout)
    while True:
        if health_file.is_file():
            try:
                result = json.loads(health_file.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise RuntimeError(f"Не удалось прочитать подтверждение запуска JARVIS: {exc}") from exc
            if not isinstance(result, dict) or result.get("status") != "ready":
                raise RuntimeError("JARVIS сообщил некорректное состояние запуска.")
            actual_version = str(result.get("version") or "").strip()
            if expected_version and actual_version != expected_version:
                raise RuntimeError(
                    f"Запущена версия {actual_version or 'неизвестна'}, "
                    f"ожидалась версия {expected_version}."
                )
            return result

        return_code = process.poll()
        if return_code is not None:
            raise RuntimeError(
                f"JARVIS завершился до подтверждения готовности (код {return_code})."
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"JARVIS не подтвердил успешный запуск за {timeout:.0f} секунд."
            )
        time.sleep(max(0.01, poll_interval))


def _terminate_process(process: subprocess.Popen) -> None:
    """Stop a failed or hung child before restoring application files."""
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=5.0)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
            process.wait(timeout=5.0)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _restart_and_verify(
    application_root: Path,
    health_file: Path,
    *,
    expected_version: str | None = None,
) -> dict:
    if health_file.exists():
        if health_file.is_dir():
            raise OSError("Путь подтверждения запуска является каталогом.")
        health_file.unlink()

    process = _restart(application_root, health_file)
    try:
        result = _wait_for_startup(
            process, health_file, expected_version=expected_version
        )
        logger = logging.getLogger("jarvis.updater")
        logger.info("JARVIS startup confirmed version=%s", result.get("version", "unknown"))
        return result
    except Exception:
        _terminate_process(process)
        raise


def _rollback_and_restart(
    backup: Path,
    root: Path,
    policy: UpdateInstallPolicy,
    health_file: Path,
    logger: logging.Logger,
) -> bool:
    try:
        logger.info("Starting rollback from %s", backup)
        rollback = UpdateRollbackService().restore(backup, root, policy=policy)
        logger.info("Rollback completed: %s files restored", rollback.restored_files)
    except Exception:
        logger.exception("Rollback failed")
        return False

    try:
        _restart_and_verify(root, health_file)
        logger.info("JARVIS restarted successfully after rollback")
        return True
    except Exception:
        logger.exception("JARVIS did not start after rollback")
        return False


def _cleanup_archive(archive: Path, application_root: Path) -> None:
    """Delete only the dedicated download temp directory, never an arbitrary parent."""
    parent = archive.parent.resolve()
    root = application_root.resolve()

    if not parent.name.startswith(_DOWNLOAD_DIRECTORY_PREFIX):
        return
    temp_root = Path(tempfile.gettempdir()).resolve()
    try:
        parent.relative_to(temp_root)
    except ValueError:
        return
    if parent == root or parent in root.parents or root in parent.parents:
        return
    if parent.is_dir():
        shutil.rmtree(parent, ignore_errors=True)


def main() -> int:
    args = _parse_args()
    root = args.root.resolve()
    archive = args.archive.resolve()
    backup = args.backup.resolve()

    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "updater.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
    )
    logger = logging.getLogger("jarvis.updater")
    health_file = archive.parent / "startup-health.json"

    try:
        logger.info("Updater started for PID %s", args.pid)
        try:
            _wait_for_process_exit(args.pid)
            policy = UpdateInstallPolicy(root)
        except Exception as wait_error:
            logger.exception("Updater could not safely begin: %s", wait_error)
            if isinstance(wait_error, TimeoutError):
                try:
                    if _is_process_running(args.pid):
                        logger.error(
                            "The original process is still running; refusing to launch a duplicate instance"
                        )
                        return 2
                except Exception:
                    logger.exception("Could not determine whether the original process is still running")
            try:
                _restart_and_verify(root, health_file)
                logger.info("Original JARVIS restarted; update was not installed")
            except Exception:
                logger.exception("Could not restart the original JARVIS process")
                return 2
            return 1

        try:
            result = UpdateInstaller().install(
                archive,
                root,
                policy=policy,
                expected_size=args.expected_size,
            )
        except Exception as install_error:
            logger.exception("Update installation failed: %s", install_error)
            return 1 if _rollback_and_restart(
                backup, root, policy, health_file, logger
            ) else 2

        logger.info("Update installed: %s files", result.installed_files)
        try:
            _restart_and_verify(
                root,
                health_file,
                expected_version=args.expected_version or None,
            )
            logger.info("Updated JARVIS started successfully")
            return 0
        except Exception as startup_error:
            logger.exception("Updated JARVIS failed its startup check: %s", startup_error)
            return 1 if _rollback_and_restart(
                backup, root, policy, health_file, logger
            ) else 2
    except Exception:
        logger.exception("Updater failed unexpectedly")
        return 2
    finally:
        _cleanup_archive(archive, root)


if __name__ == "__main__":
    sys.exit(main())
