from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler

from core.app_paths import LOG_DIR, ensure_application_dirs


_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(module)s:%(lineno)d | %(message)s"
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


def setup_logging() -> logging.Logger:
    ensure_application_dirs()
    logger = logging.getLogger("jarvis")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    logger.addHandler(_handler(LOG_DIR / "jarvis.log", logging.DEBUG))
    logger.addHandler(_handler(LOG_DIR / "errors.log", logging.ERROR))

    events = _handler(LOG_DIR / "events.log", logging.INFO)
    events.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(events)

    # Existing third-party and standard-library loggers are also captured.
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(_handler(LOG_DIR / "jarvis.log", logging.DEBUG))
    root.addHandler(_handler(LOG_DIR / "errors.log", logging.ERROR))
    logging.captureWarnings(True)

    logger.info("logging_initialized | pid=%s | python=%s | executable=%s", sys.platform, sys.version.replace("\n", " "), sys.executable)
    return logger


def log_event(event: str, **data) -> None:
    """Записывает структурированное диагностическое событие."""
    payload = {"event": event, **data}
    try:
        message = json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
    except Exception:
        message = repr(payload)
    logging.getLogger("jarvis").info(message)
