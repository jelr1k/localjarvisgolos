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

        # Имя ассистента
        self.assistant_name = QLineEdit(
            config.get("assistant_name", "JARVIS")
        )

        # Модель
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItem(config.get("model"))

        # Раздумывания
        self.thinking = QCheckBox(
            "Включить режим раздумывания"
        )
        self.thinking.setChecked(
            bool(config.get("thinking"))
        )

        # Температура
        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.05)
        self.temperature.setValue(
            float(config.get("temperature"))
        )

        # Контекст
        self.context = QSpinBox()
        self.context.setRange(512, 131072)
        self.context.setSingleStep(512)
        self.context.setValue(
            int(config.get("context_length"))
        )

        # Максимум ответа
        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(1, 131072)
        self.max_tokens.setSingleStep(256)
        self.max_tokens.setValue(
            int(config.get("max_tokens"))
        )

        # Ollama
        self.url = QLineEdit(
            config.ollama_url
        )

        # =========================
        # Форма
        # =========================

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
            "Ollama:",
            self.url
        )

        box = QGroupBox("Параметры")
        box.setLayout(form)

        # =========================
        # Кнопки
        # =========================

        refresh = QPushButton(
            "Обновить список моделей"
        )

        refresh.clicked.connect(
            self.refresh_models
        )

        save = QPushButton(
            "Сохранить настройки"
        )

        save.clicked.connect(
            self.save
        )

        # =========================
        # Layout
        # =========================

        layout = QVBoxLayout(self)

        layout.addWidget(box)
        layout.addWidget(refresh)
        layout.addWidget(save)
        layout.addStretch()

    def refresh_models(self):
        try:
            models = self.model_service.get_models()

            current = self.model.currentText()

            self.model.clear()
            self.model.addItems(models)

            if current:
                self.model.setCurrentText(
                    current
                )

        except Exception as exc:
            QMessageBox.warning(
                self,
                "Ollama",
                str(exc)
            )

    def save(self):

        # =========================
        # Сохраняем имя ассистента
        # =========================

        self.config.data["assistant_name"] = (
            self.assistant_name.text().strip()
            or "JARVIS"
        )

        # =========================
        # Остальные настройки
        # =========================

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

        self.config.data["ollama"]["base_url"] = (
            self.url.text().strip().rstrip("/")
        )

        # Сохраняем settings.json
        self.config.save()

        # Сообщаем ChatPage новое имя и модель
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
