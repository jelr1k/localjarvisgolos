import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from core.application import JarvisApplication


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Jarvis")

    try:
        jarvis = JarvisApplication()
        app.setApplicationName(jarvis.config.get("assistant_name", "JARVIS"))
        jarvis.show()
    except Exception as exc:
        QMessageBox.critical(None, "Jarvis", str(exc))
        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
