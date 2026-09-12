import logging
import sys

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
