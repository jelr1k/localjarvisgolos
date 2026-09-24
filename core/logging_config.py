from __future__ import annotations

import json
import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler

from core.app_paths import LOG_DIR, ensure_application_dirs


_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(module)s:%(lineno)d | %(message)s"
_EVENT_FORMAT = "%(message)s"
_MAX_BYTES = 10_000_000
_BACKUP_COUNT = 10


def _handler(path, level):
    handler = RotatingFileHandler(
        path,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_FORMAT))
    return handler


def _configure_logger(name: str, filename: str) -> logging.Logger:
    """Configure one subsystem logger and stop it from leaking into jarvis.log."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if not logger.handlers:
        logger.addHandler(_handler(LOG_DIR / filename, logging.DEBUG))
        logger.addHandler(_handler(LOG_DIR / "errors.log", logging.ERROR))

    return logger


def setup_logging() -> logging.Logger:
    ensure_application_dirs()

    logger = logging.getLogger("jarvis")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(_handler(LOG_DIR / "jarvis.log", logging.DEBUG))
    logger.addHandler(_handler(LOG_DIR / "errors.log", logging.ERROR))

    # Root logger is deliberately not connected to the application log files.
    # Otherwise every child logger can duplicate its records in jarvis.log.
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    root.handlers.clear()
    logging.captureWarnings(True)

    # Subsystem logs. Child loggers such as jarvis.voice.wake_word inherit
    # handlers from their subsystem parent.
    _configure_logger("jarvis.voice", "voice.log")
    _configure_logger("jarvis.ollama", "ollama.log")
    _configure_logger("jarvis.llm", "ollama.log")
    _configure_logger("jarvis.chat", "commands.log")
    _configure_logger("jarvis.router", "commands.log")
    _configure_logger("jarvis.tools", "commands.log")
    _configure_logger("jarvis.process", "commands.log")
    _configure_logger("jarvis.target_resolver", "commands.log")

    events_logger = logging.getLogger("jarvis.events")
    events_logger.setLevel(logging.INFO)
    events_logger.propagate = False
    if not events_logger.handlers:
        events_handler = RotatingFileHandler(
            LOG_DIR / "events.log",
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
        events_handler.setFormatter(logging.Formatter(_EVENT_FORMAT))
        events_logger.addHandler(events_handler)

    logger.info(
        "logging_initialized pid=%s platform=%s python=%s executable=%s cwd=%s argv=%r machine=%s",
        os.getpid(),
        sys.platform,
        sys.version.replace("\n", " "),
        sys.executable,
        os.getcwd(),
        sys.argv,
        platform.platform(),
    )
    log_event(
        "logging_initialized",
        pid=os.getpid(),
        platform=sys.platform,
        python=sys.version.replace("\n", " "),
        executable=sys.executable,
        cwd=os.getcwd(),
        argv=sys.argv,
        machine=platform.platform(),
    )
    return logger


def log_event(event: str, **data) -> None:
    """Записывает одно структурированное JSON-событие в events.log."""
    payload = {"event": event, **data}
    try:
        message = json.dumps(
            payload,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )
    except Exception:
        message = json.dumps(
            {
                "event": event,
                "serialization_error": True,
                "data": repr(data),
            },
            ensure_ascii=False,
        )
    logging.getLogger("jarvis.events").info(message)
