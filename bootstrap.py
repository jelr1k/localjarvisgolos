from __future__ import annotations

import faulthandler
import logging
import runpy
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parent
LOG_DIR = APP_ROOT / "logs"
STARTUP_LOG = LOG_DIR / "startup.log"
FATAL_LOG = LOG_DIR / "fatal.log"


# Держим файл открытым всё время работы процесса: faulthandler требует,
# чтобы переданный ему файловый дескриптор не закрывался до отключения handler.
_fatal_log_file = None


def _setup_bootstrap_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("jarvis.bootstrap")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = RotatingFileHandler(
            STARTUP_LOG,
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
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
    logger = _setup_bootstrap_logging()
    _install_exception_hooks(logger)
    _enable_fatal_error_logging()

    logger.info("Starting Jarvis bootstrap")

    try:
        runpy.run_path(str(APP_ROOT / "main.py"), run_name="__main__")
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
