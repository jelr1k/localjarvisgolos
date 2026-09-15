from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QSpinBox,
    QLineEdit,
    QPushButton,
    QMessageBox,
    QGroupBox,
)


class SettingsPage(QWidget):

    settings_changed = Signal(str, str)

    def __init__(self, config, model_service):
        super().__init__()

        self.config = config
        self.model_service = model_service

        self.assistant_name = QLineEdit(
            config.get("assistant_name", "JARVIS")
        )

        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItem(config.get("model"))

        self.thinking = QCheckBox(
            "Включить режим раздумывания"
        )
        self.thinking.setChecked(
            bool(config.get("thinking"))
        )

        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.05)
        self.temperature.setValue(
            float(config.get("temperature"))
        )

        self.context = QSpinBox()
        self.context.setRange(512, 131072)
        self.context.setSingleStep(512)
        self.context.setValue(
            int(config.get("context_length"))
        )

        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(1, 131072)
        self.max_tokens.setSingleStep(256)
        self.max_tokens.setValue(
            int(config.get("max_tokens"))
        )

        self.url = QLineEdit(
            config.ollama_url
        )

        self.microphone = QComboBox()
        self._load_microphones()

        form = QFormLayout()

        form.addRow(
            "Имя ассистента:",
            self.assistant_name
        )

        form.addRow(
            "Модель:",
            self.model
        )

        form.addRow(
            "Раздумывания:",
            self.thinking
        )

        form.addRow(
            "Температура:",
            self.temperature
        )

        form.addRow(
            "Контекст:",
            self.context
        )

        form.addRow(
            "Максимум ответа:",
            self.max_tokens
        )

        form.addRow(
            "Микрофон:",
            self.microphone
        )

        form.addRow(
            "Ollama:",
            self.url
        )

        box = QGroupBox("Параметры")
        box.setLayout(form)

        refresh = QPushButton(
            "Обновить список моделей"
        )
        refresh.clicked.connect(self.refresh_models)

        refresh_microphones = QPushButton(
            "Обновить список микрофонов"
        )
        refresh_microphones.clicked.connect(self._load_microphones)

        save = QPushButton(
            "Сохранить настройки"
        )
        save.clicked.connect(self.save)

        layout = QVBoxLayout(self)
        layout.addWidget(box)
        layout.addWidget(refresh)
        layout.addWidget(refresh_microphones)
        layout.addWidget(save)
        layout.addStretch()

    def _load_microphones(self):
        try:
            import sounddevice as sd

            current = self.config.get("voice", {}).get("input_device")
            self.microphone.blockSignals(True)
            self.microphone.clear()
            self.microphone.addItem("Системный микрофон по умолчанию", None)

            for index, device in enumerate(sd.query_devices()):
                if int(device.get("max_input_channels", 0)) <= 0:
                    continue
                name = str(device.get("name", f"Микрофон {index}"))
                hostapi = str(device.get("hostapi", ""))
                label = f"{name}  [#{index}]"
                if hostapi:
                    label += f" — {hostapi}"
                self.microphone.addItem(label, index)

            position = self.microphone.findData(current)
            self.microphone.setCurrentIndex(position if position >= 0 else 0)
        except Exception as exc:
            self.microphone.clear()
            self.microphone.addItem("Не удалось получить список микрофонов")
            self.microphone.setToolTip(str(exc))
        finally:
            self.microphone.blockSignals(False)

    def refresh_models(self):
        try:
            models = self.model_service.get_models()
            current = self.model.currentText()
            self.model.clear()
            self.model.addItems(models)
            if current:
                self.model.setCurrentText(current)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Ollama",
                str(exc)
            )

    def save(self):
        self.config.data["assistant_name"] = (
            self.assistant_name.text().strip()
            or "JARVIS"
        )

        self.config.data["model"] = (
            self.model.currentText().strip()
        )

        self.config.data["thinking"] = (
            self.thinking.isChecked()
        )

        self.config.data["temperature"] = (
            self.temperature.value()
        )

        self.config.data["context_length"] = (
            self.context.value()
        )

        self.config.data["max_tokens"] = (
            self.max_tokens.value()
        )

        self.config.data["voice"]["input_device"] = self.microphone.currentData()

        self.config.data["ollama"]["base_url"] = (
            self.url.text().strip().rstrip("/")
        )

        self.config.save()

        self.settings_changed.emit(
            self.config.get("model"),
            self.config.get(
                "assistant_name",
                "JARVIS"
            )
        )

        QMessageBox.information(
            self,
            "Настройки",
            "Настройки сохранены."
        )
