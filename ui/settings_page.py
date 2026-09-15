from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
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

        self.assistant_name = QLineEdit(config.get("assistant_name", "JARVIS"))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItem(config.get("model"))

        self.thinking = QCheckBox("Включить режим раздумывания")
        self.thinking.setChecked(bool(config.get("thinking")))

        self.temperature = QDoubleSpinBox()
        self.temperature.setRange(0.0, 2.0)
        self.temperature.setSingleStep(0.05)
        self.temperature.setValue(float(config.get("temperature")))

        self.context = QSpinBox()
        self.context.setRange(512, 131072)
        self.context.setSingleStep(512)
        self.context.setValue(int(config.get("context_length")))

        self.max_tokens = QSpinBox()
        self.max_tokens.setRange(1, 131072)
        self.max_tokens.setSingleStep(256)
        self.max_tokens.setValue(int(config.get("max_tokens")))

        self.url = QLineEdit(config.ollama_url)
        self.microphone = QComboBox()
        self._load_microphones()

        form = QFormLayout()
        form.addRow("Имя ассистента:", self.assistant_name)
        form.addRow("Модель:", self.model)
        form.addRow("Раздумывания:", self.thinking)
        form.addRow("Температура:", self.temperature)
        form.addRow("Контекст:", self.context)
        form.addRow("Максимум ответа:", self.max_tokens)
        form.addRow("Микрофон:", self.microphone)
        form.addRow("Ollama:", self.url)

        box = QGroupBox("Параметры")
        box.setLayout(form)

        refresh = QPushButton("Обновить список моделей")
        refresh.clicked.connect(self.refresh_models)

        refresh_microphones = QPushButton("Обновить список микрофонов")
        refresh_microphones.clicked.connect(self._load_microphones)

        test_microphone = QPushButton("Проверить выбранный микрофон")
        test_microphone.setToolTip(
            "Запишет 1,5 секунды с выбранного микрофона на поддерживаемой частоте."
        )
        test_microphone.clicked.connect(self._test_microphone)
        self.test_microphone = test_microphone

        save = QPushButton("Сохранить настройки")
        save.clicked.connect(self.save)

        layout = QVBoxLayout(self)
        layout.addWidget(box)
        layout.addWidget(refresh)
        layout.addWidget(refresh_microphones)
        layout.addWidget(test_microphone)
        layout.addWidget(save)
        layout.addStretch()

    def _load_microphones(self):
        try:
            import sounddevice as sd
            from voice.devices import list_input_devices

            current = self.config.get("voice", {}).get("input_device")
            self.microphone.blockSignals(True)
            self.microphone.clear()
            self.microphone.addItem("Системный микрофон по умолчанию", None)

            devices = list_input_devices(list(sd.query_devices()), list(sd.query_hostapis()))
            current_found = False
            for device in devices:
                index = int(device["index"])
                name = str(device.get("name", f"Микрофон {index}"))
                hostapi = str(device.get("hostapi_name", ""))
                self.microphone.addItem(name, index)
                item_index = self.microphone.count() - 1
                if hostapi:
                    self.microphone.setItemData(
                        item_index,
                        f"Устройство ввода через {hostapi} (индекс {index})",
                        3,
                    )
                if current is not None and index == current:
                    current_found = True
                    self.microphone.setCurrentIndex(item_index)

            if not current_found:
                self.microphone.setCurrentIndex(0)
        except Exception as exc:
            self.microphone.clear()
            self.microphone.addItem("Не удалось получить список микрофонов")
            self.microphone.setToolTip(str(exc))
        finally:
            self.microphone.blockSignals(False)

    def _test_microphone(self):
        """Record a short sample using a sample rate supported by the device."""
        import numpy as np
        import sounddevice as sd
        from voice.devices import find_supported_sample_rate

        device = self.microphone.currentData()
        channels = int(self.config.get("voice", {}).get("channels", 1))
        preferred_rate = int(self.config.get("voice", {}).get("sample_rate", 16000))
        duration = 1.5

        self.test_microphone.setEnabled(False)
        try:
            recording_rate = find_supported_sample_rate(
                device=device,
                channels=channels,
                preferred=preferred_rate,
            )
            self.test_microphone.setText(f"Слушаю 1,5 секунды ({recording_rate} Гц)...")
            QApplication.processEvents()

            audio = sd.rec(
                int(recording_rate * duration),
                samplerate=recording_rate,
                channels=channels,
                dtype="float32",
                device=device,
                blocking=True,
            )
            audio = np.asarray(audio, dtype=np.float32)
            peak = float(np.max(np.abs(audio))) if audio.size else 0.0
            rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0

            if peak < 0.003 or rms < 0.0008:
                QMessageBox.warning(
                    self,
                    "Проверка микрофона",
                    "Микрофон подключился, но сигнал почти отсутствует.\n\n"
                    "Проверьте, что выбран правильный микрофон, он не отключён в Windows "
                    "и приложению разрешён доступ к микрофону.\n\n"
                    f"Частота записи: {recording_rate} Гц\n"
                    f"Пиковый уровень: {peak:.4f}\nСредний уровень: {rms:.4f}",
                )
            else:
                QMessageBox.information(
                    self,
                    "Проверка микрофона",
                    "Микрофон работает, сигнал обнаружен.\n\n"
                    f"Частота записи: {recording_rate} Гц\n"
                    f"Пиковый уровень: {peak:.4f}\nСредний уровень: {rms:.4f}",
                )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Проверка микрофона",
                "Не удалось записать звук с выбранного микрофона.\n\n"
                f"{exc}",
            )
        finally:
            self.test_microphone.setText("Проверить выбранный микрофон")
            self.test_microphone.setEnabled(True)

    def refresh_models(self):
        try:
            models = self.model_service.get_models()
            current = self.model.currentText()
            self.model.clear()
            self.model.addItems(models)
            if current:
                self.model.setCurrentText(current)
        except Exception as exc:
            QMessageBox.warning(self, "Ollama", str(exc))

    def save(self):
        self.config.data["assistant_name"] = self.assistant_name.text().strip() or "JARVIS"
        self.config.data["model"] = self.model.currentText().strip()
        self.config.data["thinking"] = self.thinking.isChecked()
        self.config.data["temperature"] = self.temperature.value()
        self.config.data["context_length"] = self.context.value()
        self.config.data["max_tokens"] = self.max_tokens.value()

        voice_config = self.config.data.setdefault("voice", {})
        voice_config["input_device"] = self.microphone.currentData()

        self.config.data["ollama"]["base_url"] = self.url.text().strip().rstrip("/")
        self.config.save()

        self.settings_changed.emit(
            self.config.get("model"),
            self.config.get("assistant_name", "JARVIS"),
        )
        QMessageBox.information(self, "Настройки", "Настройки сохранены.")
