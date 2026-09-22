from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QGroupBox, QLabel, QVBoxLayout, QWidget

from security.permissions import PermissionManager
from tools.paths import TOOL_WORKSPACE
from tools.registry import TOOLS


class ToolsPage(QWidget):
    tools_changed = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        self.permissions = PermissionManager(config)
        self.checkboxes = {}

        title = QLabel("Инструменты Jarvis")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        workspace = QLabel(f"Рабочая папка: {TOOL_WORKSPACE}")
        workspace.setWordWrap(True)

        box = QGroupBox("Доступные инструменты")
        box_layout = QVBoxLayout(box)

        display_names = {
            "search_files": "Поиск файлов",
            "read_file": "Чтение файла",
            "create_file": "Создание файла",
            "write_file": "Запись файла",
            "delete_file": "Удаление файла",
            "rename_file": "Переименование файла",
            "copy_file": "Копирование файла",
            "move_file": "Перемещение файла",
            "create_folder": "Создание папки",
            "file_info": "Информация о файле",
            "find_application": "Поиск приложения",
            "get_process_status": "Проверка состояния приложения",
            "launch_application": "Запуск приложения",
            "minimize_application": "Сворачивание приложения",
            "close_application": "Закрытие приложения",
            "open_url": "Открытие ссылки",
        }

        for name, tool in TOOLS.items():
            checkbox = QCheckBox(display_names.get(name, name))
            checkbox.setChecked(self.permissions.is_enabled(name))
            checkbox.setToolTip(tool.get("description", ""))
            checkbox.toggled.connect(lambda value, tool_name=name: self._set_tool(tool_name, value))
            self.checkboxes[name] = checkbox
            box_layout.addWidget(checkbox)

        hint = QLabel(
            "Отключённый инструмент одновременно убирается из доступных модели и блокируется повторной проверкой при выполнении. "
            "Все файловые инструменты ограничены workspace."
        )
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(workspace)
        layout.addWidget(box)
        layout.addWidget(hint)
        layout.addStretch()

    def _set_tool(self, name, enabled):
        self.permissions.update(name, enabled)
        self.tools_changed.emit()
