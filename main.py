from __future__ import annotations

import logging
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parent


def _find_project_root() -> Path:
    """Find the Jarvis project root without relying on the current working directory."""
    for candidate in (APP_DIR, APP_DIR.parent):
        if (candidate / "core").is_dir():
            return candidate
    return APP_DIR


PROJECT_ROOT = _find_project_root()
project_root = str(PROJECT_ROOT)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


from PySide6.QtWidgets import QApplication, QMessageBox

from core.application import JarvisApplication
from core.logging_config import setup_logging


def main():
    logger = setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")

    try:
        jarvis = JarvisApplication()
        app.setApplicationName(jarvis.config.get("assistant_name", "JARVIS"))
        jarvis.show()
        logger.info("Jarvis started")
    except Exception as exc:
        logger.exception("Jarvis startup failed")
        QMessageBox.critical(None, "Jarvis", str(exc))
        sys.exit(1)

    exit_code = app.exec()
    logging.getLogger("jarvis").info("Jarvis stopped")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
