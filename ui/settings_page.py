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
        self.router_only_mode = QCheckBox("Только роутер, без LLM")
        self.router_only_mode.setChecked(bool(config.get("router_only_mode", False)))
        self.router_only_mode.setToolTip("Тестовый режим: запросы идут через Command Router. Если роутер не распознал команду, LLM не вызывается и модель не загружается.")
        self.allow_outside_workspace = QCheckBox("Работа вне Workspace")
        self.allow_outside_workspace.setChecked(bool(config.get("allow_outside_workspace", False)))
        self.allow_outside_workspace.setToolTip("Разрешает запускать приложения и файлы, расположенные вне рабочей папки Jarvis. По умолчанию доступ запрещён.")
        self.microphone = QComboBox()
        self.wake_word_enabled = QCheckBox("Включить wake word")
        self.wake_word_enabled.setChecked(bool(config.get("voice", {}).get("wake_word_enabled", True)))
        self.wake_word = QLineEdit(config.get("voice", {}).get("wake_word", "Jarvis"))
        self.wake_word.setPlaceholderText("Например: Jarvis или Компьютер")
        self.wake_word.setToolTip("Фраза, которой активируется голосовой режим вне приложения.")
        self._load_microphones()

        form = QFormLayout()
        form.addRow("Имя ассистента:", self.assistant_name)
        form.addRow("Модель:", self.model)
        form.addRow("Температура:", self.temperature)
        form.addRow("Контекст:", self.context)
        form.addRow("Максимум ответа:", self.max_tokens)
        form.addRow("Микрофон:", self.microphone)
        form.addRow("Wake word:", self.wake_word)
        form.addRow("", self.wake_word_enabled)
        form.addRow("Ollama:", self.url)
        form.addRow("Режим тестирования:", self.router_only_mode)
        form.addRow("Безопасность:", self.allow_outside_workspace)

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
            from voice.devices import list_input_devices, _normalize_name

            voice_config = self.config.get("voice", {})
            current_index = voice_config.get("input_device")
            current_name = voice_config.get("input_device_name")

            self.microphone.blockSignals(True)
            self.microphone.clear()
            self.microphone.addItem("Системный микрофон по умолчанию", None)

            devices = list_input_devices(list(sd.query_devices()), list(sd.query_hostapis()))
            current_found = False
            normalized_current_name = _normalize_name(current_name or "")

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

                same_name = normalized_current_name and _normalize_name(name) == normalized_current_name
                same_index = current_index is not None and index == current_index
                if same_name or (not current_name and same_index):
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
        self.config.data["temperature"] = self.temperature.value()
        self.config.data["context_length"] = self.context.value()
        self.config.data["max_tokens"] = self.max_tokens.value()

        self.config.data["router_only_mode"] = self.router_only_mode.isChecked()
        self.config.data["allow_outside_workspace"] = self.allow_outside_workspace.isChecked()

        voice_config = self.config.data.setdefault("voice", {})
        selected_device = self.microphone.currentData()
        voice_config["input_device"] = selected_device
        voice_config["input_device_name"] = (
            self.microphone.currentText().strip()
            if selected_device is not None
            else None
        )
        voice_config["wake_word_enabled"] = self.wake_word_enabled.isChecked()
        voice_config["wake_word"] = self.wake_word.text().strip() or "Jarvis"

        self.config.data["ollama"]["base_url"] = self.url.text().strip().rstrip("/")
        self.config.save()

        self.settings_changed.emit(
            self.config.get("model"),
            self.config.get("assistant_name", "JARVIS"),
        )
        QMessageBox.information(self, "Настройки", "Настройки сохранены.")
