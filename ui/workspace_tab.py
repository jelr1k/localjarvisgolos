from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.workspace_view_model import WorkspaceObject, WorkspaceViewModel


class AliasDialog(QDialog):
    def __init__(self, parent: QWidget, obj: WorkspaceObject, save_callback):
        super().__init__(parent)
        self.setWindowTitle(f"Алиасы: {obj.entry.name}")
        self.resize(460, 360)
        self._save_callback = save_callback

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Объект: {obj.entry.name}"))
        layout.addWidget(QLabel(f"Путь: {obj.entry.relative_path}"))
        layout.addWidget(QLabel("Автоматические алиасы:"))
        automatic = QLabel("\n".join(f"• {item}" for item in obj.automatic_aliases) or "нет")
        automatic.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(automatic)

        layout.addWidget(QLabel("Пользовательские алиасы (по одному на строку):"))
        self.editor = QLineEdit()
        self.editor.setPlaceholderText("например: мой стим")
        self.list_widget = QListWidget()
        self.list_widget.addItems(obj.user_aliases)
        layout.addWidget(self.list_widget)

        row = QHBoxLayout()
        row.addWidget(self.editor)
        add = QPushButton("Добавить")
        add.clicked.connect(self._add)
        row.addWidget(add)
        remove = QPushButton("Удалить выбранный")
        remove.clicked.connect(self._remove)
        row.addWidget(remove)
        layout.addLayout(row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _add(self):
        alias = self.editor.text().strip()
        if alias:
            self.list_widget.addItem(alias)
            self.editor.clear()

    def _remove(self):
        item = self.list_widget.currentItem()
        if item:
            self.list_widget.takeItem(self.list_widget.row(item))

    def _save(self):
        aliases = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        try:
            self._save_callback(aliases)
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось сохранить", str(exc))
            return
        self.accept()


class WorkspaceTab(QWidget):
    """Read-only overview of Workspace with direct alias management."""

    def __init__(self, workspace: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.model = WorkspaceViewModel(workspace)
        self.objects: list[WorkspaceObject] = []

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel(f"Workspace: {self.model.index.workspace}"))
        header.addStretch()
        refresh = QPushButton("Обновить")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._selection_changed)
        root.addWidget(self.list_widget)

        self.details = QLabel("Выберите объект")
        self.details.setWordWrap(True)
        root.addWidget(self.details)

        actions = QHBoxLayout()
        self.alias_button = QPushButton("Настроить алиасы")
        self.alias_button.setEnabled(False)
        self.alias_button.clicked.connect(self._edit_aliases)
        actions.addWidget(self.alias_button)
        actions.addStretch()
        root.addLayout(actions)

        self.refresh()

    def refresh(self):
        self.objects = self.model.refresh()
        self.list_widget.clear()
        for obj in self.objects:
            label = obj.entry.relative_path
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, obj)
            self.list_widget.addItem(item)
        self._selection_changed(self.list_widget.currentRow())

    def _selection_changed(self, row: int):
        if row < 0 or row >= len(self.objects):
            self.alias_button.setEnabled(False)
            self.details.setText("Выберите объект")
            return
        obj = self.objects[row]
        automatic = ", ".join(obj.automatic_aliases) or "нет"
        user = ", ".join(obj.user_aliases) or "нет"
        self.details.setText(
            f"Имя: {obj.entry.name}\n"
            f"Тип: {obj.entry.category}\n"
            f"Путь: {obj.entry.relative_path}\n\n"
            f"Автоматические алиасы: {automatic}\n"
            f"Пользовательские алиасы: {user}"
        )
        self.alias_button.setEnabled(True)

    def _edit_aliases(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.objects):
            return
        obj = self.objects[row]
        dialog = AliasDialog(self, obj, lambda aliases: self.model.set_aliases(obj.entry, aliases))
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            self.list_widget.setCurrentRow(row)
