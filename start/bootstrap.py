from __future__ import annotations

import faulthandler
import logging
import runpy
import sys
import threading
from logging import FileHandler
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent


def _find_project_root() -> Path:
    """Find the Jarvis project root without relying on the current working directory."""
    for candidate in (APP_DIR, APP_DIR.parent):
        if (candidate / "core").is_dir():
            return candidate
    # During unusual/partial layouts, keep the current file's directory as the
    # safest fallback. The normal project layout is covered above.
    return APP_DIR


PROJECT_ROOT = _find_project_root()
LOG_DIR = PROJECT_ROOT / "logs"
STARTUP_LOG = LOG_DIR / "startup.log"
FATAL_LOG = LOG_DIR / "fatal.log"

# Держим файл открытым всё время работы процесса: faulthandler требует,
# чтобы переданный ему файловый дескриптор не закрывался до отключения handler.
_fatal_log_file = None


def _clear_previous_logs() -> None:
    """Start every Jarvis run with a clean set of diagnostic logs."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    for path in LOG_DIR.glob("*.log*"):
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            # A stale log may be temporarily locked by another process.
            # Do not prevent Jarvis from starting because of that.
            pass


def _setup_bootstrap_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("jarvis.bootstrap")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = FileHandler(STARTUP_LOG, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
        )
        logger.addHandler(handler)

    return logger


def _install_exception_hooks(logger: logging.Logger) -> None:
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.error(
            "Unhandled exception before/while Jarvis was running",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    def handle_thread_exception(args: threading.ExceptHookArgs):
        logger.error(
            "Unhandled exception in thread %s",
            getattr(args.thread, "name", "unknown"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = handle_exception
    threading.excepthook = handle_thread_exception


def _enable_fatal_error_logging():
    global _fatal_log_file
    _fatal_log_file = open(FATAL_LOG, "a", encoding="utf-8")
    faulthandler.enable(file=_fatal_log_file, all_threads=True)


def main() -> int:
    _clear_previous_logs()
    logger = _setup_bootstrap_logging()

    # bootstrap.py may live in the repository root or in start/.
    # Make the project root importable instead of depending on cwd/sys.path.
    project_root = str(PROJECT_ROOT)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    _install_exception_hooks(logger)
    _enable_fatal_error_logging()

    logger.info("Starting Jarvis bootstrap")

    try:
        runpy.run_path(str(APP_DIR / "main.py"), run_name="__main__")
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if code != 0:
            logger.error("Jarvis exited during startup/runtime with code %s", code)
        else:
            logger.info("Jarvis exited normally")
        return code
    except BaseException:
        logger.exception("Jarvis failed to start or crashed before normal shutdown")
        return 1
    finally:
        logger.info("Jarvis bootstrap finished")

    return 0


if __name__ == "__main__":
    sys.exit(main())
