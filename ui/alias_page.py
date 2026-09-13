from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.alias_manager import AliasError, AliasManager


CATEGORY_LABELS = {
    "applications": "Приложение",
    "files": "Файл",
    "folders": "Папка",
    "actions": "Действие",
}


class AliasPage(QWidget):
    """GUI для просмотра и редактирования пользовательских алиасов."""

    def __init__(self, alias_manager: AliasManager):
        super().__init__()
        self.alias_manager = alias_manager
        self._editing_key = None

        title = QLabel("Алиасы и названия")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        hint = QLabel(
            "Здесь можно задать несколько названий одному приложению, файлу, папке или действию. "
            "Для файлов и папок указывай путь относительно workspace."
        )
        hint.setWordWrap(True)

        self.items = QListWidget()
        self.items.currentItemChanged.connect(self._load_selected)

        self.category = QComboBox()
        self.category.addItem(CATEGORY_LABELS["applications"], "applications")
        self.category.addItem(CATEGORY_LABELS["files"], "files")
        self.category.addItem(CATEGORY_LABELS["folders"], "folders")
        self.category.addItem(CATEGORY_LABELS["actions"], "actions")
        self.category.currentIndexChanged.connect(self._category_changed)

        self.target = QLineEdit()
        self.target.setPlaceholderText("Например: Discord или notes/todo.txt")

        self.aliases = QTextEdit()
        self.aliases.setPlaceholderText("По одному алиасу на строку\nнапример:\nдискорд\nдс\nds")
        self.aliases.setMinimumHeight(150)

        form = QFormLayout()
        form.addRow("Тип:", self.category)
        form.addRow("Реальное имя / путь:", self.target)
        form.addRow("Названия:", self.aliases)

        self.new_button = QPushButton("Новый")
        self.save_button = QPushButton("Сохранить")
        self.delete_button = QPushButton("Удалить")
        self.reset_button = QPushButton("Сбросить")

        self.new_button.clicked.connect(self._new)
        self.save_button.clicked.connect(self._save)
        self.delete_button.clicked.connect(self._delete)
        self.reset_button.clicked.connect(self._clear_form)

        buttons = QHBoxLayout()
        buttons.addWidget(self.new_button)
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.delete_button)
        buttons.addWidget(self.reset_button)

        editor = QVBoxLayout()
        editor.addWidget(QLabel("Редактор"))
        editor.addLayout(form)
        editor.addLayout(buttons)
        editor.addStretch()

        content = QHBoxLayout()
        content.addWidget(self.items, 1)
        editor_widget = QWidget()
        editor_widget.setLayout(editor)
        content.addWidget(editor_widget, 2)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addLayout(content)

        self.refresh()
        self._new()

    def refresh(self):
        current_key = self._editing_key
        self.items.blockSignals(True)
        self.items.clear()
        for entry in self.alias_manager.list_objects():
            label = f"[{CATEGORY_LABELS.get(entry['category'], entry['category'])}] {entry['target']}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, (entry["category"], entry["target"]))
            self.items.addItem(item)
        self.items.blockSignals(False)
        if current_key:
            self._select_key(current_key)

    def _category_changed(self):
        category = self.category.currentData()
        if category == "actions":
            self.target.setPlaceholderText("Например: launch, search, delete, status")
        elif category == "applications":
            self.target.setPlaceholderText("Например: Discord или Prism Launcher")
        elif category == "files":
            self.target.setPlaceholderText("Путь относительно workspace, например: notes/todo.txt")
        else:
            self.target.setPlaceholderText("Путь относительно workspace, например: projects")

    def _load_selected(self, current, previous=None):
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        if not key:
            return
        category, target = key
        self._editing_key = key
        index = self.category.findData(category)
        if index >= 0:
            self.category.blockSignals(True)
            self.category.setCurrentIndex(index)
            self.category.blockSignals(False)
            self._category_changed()
        self.target.setText(target)
        self.aliases.setPlainText("\n".join(self.alias_manager.get_aliases(category, target)))

    def _new(self):
        self._editing_key = None
        self.items.clearSelection()
        self._clear_form()

    def _clear_form(self):
        self.target.clear()
        self.aliases.clear()
        self._category_changed()
        self.target.setFocus()

    def _save(self):
        category = self.category.currentData()
        target = self.target.text().strip()
        aliases = [line.strip() for line in self.aliases.toPlainText().splitlines() if line.strip()]

        if not target:
            QMessageBox.warning(self, "Алиасы", "Укажи реальное имя или путь объекта.")
            return

        if not aliases:
            aliases = self.alias_manager.default_aliases(category, target)

        old_key = self._editing_key
        if old_key == (category, target):
            try:
                self.alias_manager.set_aliases(category, target, aliases)
            except AliasError as exc:
                QMessageBox.warning(self, "Алиасы", str(exc))
                return
            except OSError as exc:
                QMessageBox.critical(self, "Алиасы", f"Не удалось сохранить aliases.json: {exc}")
                return
        else:
            try:
                self.alias_manager.set_aliases(category, target, aliases)
            except AliasError as exc:
                QMessageBox.warning(self, "Алиасы", str(exc))
                return
            except OSError as exc:
                QMessageBox.critical(self, "Алиасы", f"Не удалось сохранить aliases.json: {exc}")
                return

            if old_key:
                old_category, old_target = old_key
                try:
                    self.alias_manager.remove_object(old_category, old_target)
                except OSError as exc:
                    QMessageBox.critical(
                        self,
                        "Алиасы",
                        f"Новая запись сохранена, но старую запись не удалось удалить из aliases.json: {exc}",
                    )
                    return

        self._editing_key = (category, target)
        self.refresh()
        self._select_key(self._editing_key)

    def _select_key(self, key):
        for row in range(self.items.count()):
            item = self.items.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                self.items.setCurrentItem(item)
                break

    def _delete(self):
        if not self._editing_key:
            return
        category, target = self._editing_key
        answer = QMessageBox.question(
            self,
            "Удалить алиасы",
            f"Удалить запись «{target}» и все её алиасы?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.alias_manager.remove_object(category, target)
        except OSError as exc:
            QMessageBox.critical(self, "Алиасы", f"Не удалось сохранить aliases.json: {exc}")
            return
        self.refresh()
        self._new()
