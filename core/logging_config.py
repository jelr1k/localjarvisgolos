from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from core.app_paths import LOG_DIR, ensure_application_dirs


def setup_logging() -> logging.Logger:
    ensure_application_dirs()
    logger = logging.getLogger("jarvis")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        LOG_DIR / "jarvis.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    return logger
