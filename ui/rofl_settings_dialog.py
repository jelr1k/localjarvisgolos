from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox, QVBoxLayout


class RoflSettingsDialog(QDialog):
    """Секретное окно настройки вероятностей рофлов."""

    def __init__(self, controller, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("Настройки рофлов")
        self.setModal(True)
        self.resize(420, 180)

        settings = controller.get_rofl_settings()

        self.chance = QDoubleSpinBox()
        self.chance.setRange(0.0, 100.0)
        self.chance.setDecimals(1)
        self.chance.setSingleStep(1.0)
        self.chance.setSuffix(" %")
        self.chance.setValue(float(settings.get("chance", 0.12)) * 100.0)

        self.demon_chance = QDoubleSpinBox()
        self.demon_chance.setRange(0.0, 100.0)
        self.demon_chance.setDecimals(1)
        self.demon_chance.setSingleStep(1.0)
        self.demon_chance.setSuffix(" %")
        self.demon_chance.setValue(float(settings.get("demon_chance", 0.15)) * 100.0)

        form = QFormLayout()
        form.addRow("Шанс рофла:", self.chance)
        form.addRow("Шанс демонического рофла:", self.demon_chance)

        box = QGroupBox("Служебные настройки")
        box.setLayout(form)

        buttons = QDialogButtonBox()
        save = buttons.addButton("Сохранить рофлы", QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        save.clicked.connect(self._save)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(box)
        root.addWidget(buttons)

    def _save(self):
        self.controller.save_rofl_settings(
            self.chance.value() / 100.0,
            self.demon_chance.value() / 100.0,
        )
        self.accept()
