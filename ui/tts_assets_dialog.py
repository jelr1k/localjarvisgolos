from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)


class TTSAssetsDialog(QDialog):
    """Small UI for prepared phrase assets and TTS runtime diagnostics.

    All synthesis and asset operations go through SettingsController/TTSService;
    this view never imports a concrete engine or handles audio playback itself.
    """

    _VOICES = (
        ("Дмитрий · русский · medium", "ru_RU-dmitri-medium"),
        ("Ирина · русский · medium", "ru_RU-irina-medium"),
        ("Руслан · русский · medium", "ru_RU-ruslan-medium"),
    )

    def __init__(self, controller, current_voice: str | None = None, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._import_running = False
        self.setWindowTitle("Готовые озвучки и статистика TTS")
        self.resize(660, 650)

        root = QVBoxLayout(self)
        description = QLabel(
            "Импортируй WAV и укажи текст, которому он соответствует. "
            "При точном совпадении текста Jarvis сможет использовать запись вместо синтеза. "
            "Поддерживается PCM WAV, 16 бит, mono/stereo."
        )
        description.setWordWrap(True)
        root.addWidget(description)

        form = QFormLayout()
        self.voice = QComboBox()
        for label, value in self._VOICES:
            self.voice.addItem(label, value)
        index = self.voice.findData(current_voice)
        if index >= 0:
            self.voice.setCurrentIndex(index)
        form.addRow("Голос записи:", self.voice)

        self.response_key = QLineEdit()
        self.response_key.setPlaceholderText("Например: greeting.hello или router.launch.success")
        form.addRow("Ключ реплики:", self.response_key)

        self.response_text = QPlainTextEdit()
        self.response_text.setPlaceholderText("Точный текст, при котором нужно использовать эту запись")
        self.response_text.setMaximumHeight(90)
        form.addRow("Текст реплики:", self.response_text)
        root.addLayout(form)

        import_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText("Путь к готовому WAV-файлу")
        choose = QPushButton("Выбрать WAV…")
        choose.clicked.connect(self._choose_file)
        self.import_button = QPushButton("Импортировать")
        self.import_button.clicked.connect(self._import_file)
        import_row.addWidget(self.file_path, 1)
        import_row.addWidget(choose)
        import_row.addWidget(self.import_button)
        root.addLayout(import_row)

        root.addWidget(QLabel("Подготовленные реплики для выбранного голоса:"))
        self.assets_list = QListWidget()
        root.addWidget(self.assets_list, 1)

        asset_buttons = QHBoxLayout()
        self.play_button = QPushButton("Прослушать")
        self.play_button.clicked.connect(self._play_selected)
        self.remove_button = QPushButton("Удалить запись")
        self.remove_button.clicked.connect(self._remove_selected)
        refresh_button = QPushButton("Обновить")
        refresh_button.clicked.connect(self.refresh)
        asset_buttons.addWidget(self.play_button)
        asset_buttons.addWidget(self.remove_button)
        asset_buttons.addStretch(1)
        asset_buttons.addWidget(refresh_button)
        root.addLayout(asset_buttons)

        self.stats_label = QLabel()
        self.stats_label.setWordWrap(True)
        root.addWidget(self.stats_label)
        self.status_label = QLabel("Готово.")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        cache_row = QHBoxLayout()
        self.clear_cache_button = QPushButton("Очистить кеш синтеза")
        self.clear_cache_button.clicked.connect(self._clear_cache)
        close_button = QPushButton("Закрыть")
        close_button.clicked.connect(self.accept)
        cache_row.addWidget(self.clear_cache_button)
        cache_row.addStretch(1)
        cache_row.addWidget(close_button)
        root.addLayout(cache_row)

        self.voice.currentIndexChanged.connect(self.refresh)
        self.assets_list.currentRowChanged.connect(self._update_asset_buttons)
        self.controller.tts_state_changed.connect(self._on_tts_state_changed)
        if hasattr(self.controller, "tts_asset_finished"):
            self.controller.tts_asset_finished.connect(self._on_import_finished)
        self.refresh()

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите готовую озвучку", str(Path.home()), "WAV-аудио (*.wav)"
        )
        if path:
            self.file_path.setText(path)

    def _import_file(self):
        voice = self.voice.currentData()
        key = self.response_key.text().strip()
        text = self.response_text.toPlainText().strip()
        path = self.file_path.text().strip()
        if not key or not text or not path:
            QMessageBox.warning(self, "Импорт озвучки", "Заполни ключ, текст реплики и выбери WAV-файл.")
            return
        if Path(path).suffix.casefold() != ".wav":
            QMessageBox.warning(self, "Импорт озвучки", "Сейчас принимаются только файлы .wav.")
            return
        self._import_running = True
        self.import_button.setEnabled(False)
        self.status_label.setText("Импортирую и проверяю WAV-файл в фоновом потоке…")
        try:
            self.controller.import_tts_prepared_audio(voice, key, text, path)
        except Exception as exc:
            self._import_running = False
            self.import_button.setEnabled(True)
            self.status_label.setText(f"Не удалось начать импорт: {exc}")

    def _on_import_finished(self, key, success, error):
        self._import_running = False
        self.import_button.setEnabled(True)
        if success:
            self.status_label.setText(f"Готовая реплика «{key}» импортирована. Совпадающий текст будет искать её автоматически.")
            self.response_key.clear()
            self.file_path.clear()
            self.refresh()
        else:
            self.status_label.setText(f"Ошибка импорта «{key}»: {error or 'неизвестная ошибка'}")

    def _selected_entry(self):
        item = self.assets_list.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item is not None else None

    def _play_selected(self):
        entry = self._selected_entry()
        if not entry:
            return
        if self.controller.play_tts_prepared_audio(entry["voice_id"], entry["response_key"]):
            self.status_label.setText(f"В очереди воспроизведения: {entry['response_key']}")
        else:
            self.status_label.setText("Не удалось поставить готовую запись в очередь воспроизведения.")

    def _remove_selected(self):
        entry = self._selected_entry()
        if not entry:
            return
        answer = QMessageBox.question(
            self,
            "Удалить готовую озвучку",
            f"Удалить запись «{entry['response_key']}»? Это не затронет кеш динамической озвучки.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        if self.controller.remove_tts_prepared_audio(entry["voice_id"], entry["response_key"]):
            self.status_label.setText(f"Запись «{entry['response_key']}» удалена.")
            self.refresh()
        else:
            self.status_label.setText("Запись не найдена или уже удалена.")

    def _clear_cache(self):
        answer = QMessageBox.question(
            self,
            "Очистить кеш TTS",
            "Удалить только временный кеш генерации? Подготовленные реплики и модели голосов останутся на месте.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed = self.controller.clear_tts_audio_cache()
        self.status_label.setText(f"Удалено файлов кеша: {removed}.")
        self.refresh()

    def _on_tts_state_changed(self, state, message):
        if state == "error" or state in {"downloading", "synthesizing", "speaking"}:
            self.status_label.setText(message)
        self._refresh_stats()

    def _update_asset_buttons(self, _row=-1):
        selected = self._selected_entry() is not None
        self.play_button.setEnabled(selected)
        self.remove_button.setEnabled(selected)

    def _refresh_stats(self):
        stats = self.controller.get_tts_audio_stats()
        if not stats:
            self.stats_label.setText("Статистика TTS недоступна: сервис не подключён.")
            return
        metrics = stats.get("metrics", {})
        self.stats_label.setText(
            "Подготовленные записи: {prepared} ({prepared_size}); кеш: {cached} файлов, {cache_size} / {limit}; "
            "запросы: {requests}, синтезировано: {synth}, попадания в записи/кеш: {prepared_hits}/{cache_hits}, "
            "ошибки: {errors}, fallback: {fallback}, отклонено очередью: {rejected}, время синтеза: {seconds:.2f} с".format(
                prepared=stats.get("prepared_count", 0),
                prepared_size=self._format_bytes(stats.get("prepared_bytes", 0)),
                cached=stats.get("cache_count", 0),
                cache_size=self._format_bytes(stats.get("cache_bytes", 0)),
                limit=self._format_bytes(stats.get("cache_limit_bytes", 0)),
                requests=metrics.get("requests", 0),
                synth=metrics.get("successful_syntheses", 0),
                prepared_hits=metrics.get("prepared_audio_hits", 0),
                cache_hits=metrics.get("cache_hits", 0),
                errors=metrics.get("errors", 0),
                fallback=metrics.get("fallback_uses", 0),
                rejected=metrics.get("queue_rejections", 0),
                seconds=metrics.get("synthesis_seconds_total", 0.0),
            )
        )

    @staticmethod
    def _format_bytes(value):
        value = max(0, int(value))
        for unit in ("Б", "КБ", "МБ", "ГБ"):
            if value < 1024 or unit == "ГБ":
                return f"{value} {unit}" if unit == "Б" else f"{value / (1024 if unit != 'Б' else 1):.1f} {unit}"
            value //= 1024
        return f"{value} Б"

    def refresh(self, *_):
        selected_voice = self.voice.currentData()
        self.assets_list.clear()
        entries = self.controller.list_tts_prepared_audio(selected_voice)
        for entry in entries:
            preview = entry.get("text_preview") or "без привязанного текста"
            item = QListWidgetItem(f"{entry['response_key']}  ·  {preview}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self.assets_list.addItem(item)
        self._update_asset_buttons()
        self._refresh_stats()
