import sys

from PySide6.QtWidgets import QApplication

from core.application import JarvisApplication


def main():
    app = QApplication(sys.argv)

    app.setApplicationName("JARVIS")

    try:
        jarvis = JarvisApplication()
        jarvis.show()

    except Exception as exc:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.critical(
            None,
            "JARVIS",
            str(exc)
        )

        sys.exit(1)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
