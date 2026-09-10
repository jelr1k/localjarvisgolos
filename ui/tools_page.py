from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QCheckBox, QVBoxLayout, QGroupBox, QWidget

from tools.paths import TOOL_WORKSPACE


class ToolsPage(QWidget):
    tools_changed = Signal()

    def __init__(self, config):
        super().__init__()
        self.config = config
        tools = config.get("tools", {})

        title = QLabel("Инструменты JARVIS")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        workspace = QLabel(f"Рабочая папка: {TOOL_WORKSPACE}")
        workspace.setWordWrap(True)

        self.delete_file = QCheckBox("Удаление файлов")
        self.delete_file.setToolTip(
            "Разрешает удалять отдельные файлы внутри рабочей папки после подтверждения."
        )
        self.delete_file.setChecked(bool(tools.get("delete_file", True)))
        self.delete_file.toggled.connect(
            lambda value: self._set_tool("delete_file", value)
        )

        self.launch_application = QCheckBox("Запуск файлов и ярлыков")
        self.launch_application.setToolTip(
            "Разрешает открывать и запускать файлы, программы и ярлыки внутри рабочей папки."
        )
        self.launch_application.setChecked(
            bool(tools.get("launch_application", True))
        )
        self.launch_application.toggled.connect(
            lambda value: self._set_tool("launch_application", value)
        )

        box = QGroupBox("Доступные инструменты")
        box_layout = QVBoxLayout(box)
        box_layout.addWidget(self.delete_file)
        box_layout.addWidget(self.launch_application)

        hint = QLabel(
            "Отключённый инструмент не передаётся модели и дополнительно блокируется при выполнении."
        )
        hint.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(workspace)
        layout.addWidget(box)
        layout.addWidget(hint)
        layout.addStretch()

    def _set_tool(self, name, enabled):
        self.config.data.setdefault("tools", {})[name] = bool(enabled)
        self.config.save()
        self.tools_changed.emit()
