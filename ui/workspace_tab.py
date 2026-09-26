from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
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




class AliasDialog(QDialog):
    def __init__(self, parent: QWidget, obj, save_callback):
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
        self.editor = QListWidget()
        self.editor.addItems(obj.user_aliases)
        layout.addWidget(self.editor)

        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("например: мой стим")
        row.addWidget(self.input)
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
        alias = self.input.text().strip()
        if alias:
            self.editor.addItem(alias)
            self.input.clear()

    def _remove(self):
        item = self.editor.currentItem()
        if item:
            self.editor.takeItem(self.editor.row(item))

    def _save(self):
        aliases = [self.editor.item(i).text() for i in range(self.editor.count())]
        try:
            self._save_callback(aliases)
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось сохранить", str(exc))
            return
        self.accept()


class WorkspaceTab(QWidget):
    """Workspace is the entry point for adding and resolving workspace objects."""

    def __init__(
        self,
        controller,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.controller = controller
        self.objects: list[WorkspaceObject] = []
        self.setAcceptDrops(True)

        root = QVBoxLayout(self)
        header = QHBoxLayout()
        header.addWidget(QLabel(f"Workspace: {self.controller.workspace}"))
        header.addStretch()

        add = QPushButton("Добавить файл")
        add.clicked.connect(self._choose_file)
        header.addWidget(add)

        refresh = QPushButton("Обновить")
        refresh.clicked.connect(self.refresh)
        header.addWidget(refresh)
        root.addLayout(header)

        self.drop_zone = QLabel("Перетащи файл сюда\nили нажми «Добавить файл»")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setMinimumHeight(80)
        self.drop_zone.setStyleSheet(
            "border: 2px dashed palette(mid); padding: 14px; border-radius: 8px;"
        )
        root.addWidget(self.drop_zone)

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

    def dragEnterEvent(self, event: QDragEnterEvent):
        if self._mime_has_files(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        paths = self._mime_file_paths(event.mimeData())
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        for path in paths:
            self._import_file(path)

    @staticmethod
    def _mime_has_files(mime_data: QMimeData) -> bool:
        return bool(mime_data.hasUrls() and any(url.isLocalFile() for url in mime_data.urls()))

    @staticmethod
    def _mime_file_paths(mime_data: QMimeData) -> list[Path]:
        paths: list[Path] = []
        for url in mime_data.urls():
            if not url.isLocalFile():
                continue
            path = Path(url.toLocalFile())
            if path.is_file():
                paths.append(path)
        return paths

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Добавить файл в Workspace",
            "",
            "Все файлы (*.*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if path:
            self._import_file(Path(path))

    def _import_file(self, source: Path):
        try:
            target = self.controller.add_file(source)
        except FileExistsError as exc:
            QMessageBox.information(self, "Workspace", str(exc))
            self.refresh()
            return
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "Workspace", str(exc))
            return

        self.refresh()
        for row, obj in enumerate(self.objects):
            if obj.entry.path == target.resolve():
                self.list_widget.setCurrentRow(row)
                break

    def refresh(self):
        self.objects = self.controller.refresh()
        self.list_widget.clear()
        for obj in self.objects:
            item = QListWidgetItem(obj.entry.relative_path)
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
        self.alias_button.setEnabled(obj.entry.category in {"applications", "files"})

    def _edit_aliases(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self.objects):
            return
        obj = self.objects[row]
        if obj.entry.category not in {"applications", "files"}:
            return
        dialog = AliasDialog(self, obj, lambda aliases: self.controller.set_aliases(obj.entry, aliases)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            self.list_widget.setCurrentRow(row)
