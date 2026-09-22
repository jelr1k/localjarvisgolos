from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView


class CommandsWindow(QDialog):
    """Простое окно со справочником команд текущего Command Router."""

    def __init__(self, router, parent=None):
        super().__init__(parent)
        self.router = router
        self.setWindowTitle("Команды Command Router")
        self.resize(760, 620)

        title = QLabel("Команды, которые распознаёт Command Router")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Команда", "Как распознаётся"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh)

        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(refresh_button)
        buttons.addStretch()
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

        self.refresh()

    def refresh(self):
        self.table.setRowCount(0)
        for item in self.router.command_catalog():
            row = self.table.rowCount()
            self.table.insertRow(row)

            name_item = QTableWidgetItem(str(item["name"]))
            name_item.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

            commands = "\n".join(f"• {command}" for command in item["commands"])
            commands_item = QTableWidgetItem(commands)
            commands_item.setTextAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, commands_item)

        self.table.resizeRowsToContents()
