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

        for name, tool in TOOLS.items():
            checkbox = QCheckBox(name)
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
