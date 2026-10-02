from __future__ import annotations

from pathlib import Path
import webbrowser

from core.version import APP_VERSION
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QComboBox,QCheckBox,QDoubleSpinBox,QSpinBox,QLineEdit,QPushButton,QMessageBox,QGroupBox,QHBoxLayout,QFileDialog,QLabel,QProgressBar

class SettingsPage(QWidget):
    settings_changed=Signal(str,str)
    _WHISPER_PRESETS=(("Small","small"),("Medium","medium"),("Large-v3","large-v3"),("Локальная модель",None))

    def __init__(self,controller):
        super().__init__();self.controller=controller;self._refresh_running=False;self._whisper_download_running=False
        get=controller.get
        self.assistant_name=QLineEdit(get("assistant_name","JARVIS"));self.model=QComboBox();self.model.setEditable(True);self.model.addItem(get("model"))
        self.temperature=QDoubleSpinBox();self.temperature.setRange(0,2);self.temperature.setSingleStep(.05);self.temperature.setValue(float(get("temperature")))
        self.context=QSpinBox();self.context.setRange(512,131072);self.context.setSingleStep(512);self.context.setValue(int(get("context_length")))
        self.max_tokens=QSpinBox();self.max_tokens.setRange(1,131072);self.max_tokens.setSingleStep(256);self.max_tokens.setValue(int(get("max_tokens")))
        voice=get("voice",{})
        self.whisper_cpu_threads=QSpinBox();self.whisper_cpu_threads.setRange(1,12);self.whisper_cpu_threads.setValue(max(1,min(12,int(voice.get("cpu_threads",4)))));self.whisper_cpu_threads.setToolTip("Количество CPU-потоков, выделяемых faster-whisper для распознавания. Для Ryzen 5 3600 можно начать с 4–6 и сравнить время.")
        self.whisper_beam_size=QSpinBox();self.whisper_beam_size.setRange(1,20);self.whisper_beam_size.setValue(max(1,min(20,int(voice.get("beam_size",5)))));self.whisper_beam_size.setToolTip("Beam size задаёт ширину поиска вариантов при распознавании. Меняй его и сравнивай время и качество в статистике Whisper.")
        self.whisper_vad=QCheckBox("Использовать VAD");self.whisper_vad.setChecked(bool(voice.get("vad_filter",True)));self.whisper_vad.setToolTip("Определяет участки аудио с речью и помогает игнорировать тишину.")
        self.whisper_timestamps=QCheckBox("Использовать таймкоды");self.whisper_timestamps.setChecked(not bool(voice.get("without_timestamps",True)));self.whisper_timestamps.setToolTip("Сохранять временные позиции распознанных фрагментов.")
        self.whisper_previous=QCheckBox("Учитывать предыдущий текст");self.whisper_previous.setChecked(bool(voice.get("condition_on_previous_text",False)));self.whisper_previous.setToolTip("Передавать предыдущий распознанный текст как контекст для следующего фрагмента.")
        self.url=QLineEdit(controller.ollama_url);self.router_only_mode=QCheckBox("Только роутер, без LLM");self.router_only_mode.setChecked(bool(get("router_only_mode",False)))
        self.allow_outside_workspace=QCheckBox("Работа вне Workspace (пока только открытие приложений вне)");self.allow_outside_workspace.setChecked(bool(get("allow_outside_workspace",False)))
        self.microphone=QComboBox()
        self.whisper_model=QComboBox();[self.whisper_model.addItem(label,value) for label,value in self._WHISPER_PRESETS]
        current_whisper=str(voice.get("model","small") or "small");idx=self.whisper_model.findData(current_whisper);self.whisper_local_path=QLineEdit();self.whisper_local_path.setPlaceholderText("Путь к папке модели faster-whisper")
        browse=QPushButton("Выбрать");browse.clicked.connect(self._choose_whisper_model)
        row=QHBoxLayout();row.setContentsMargins(0,0,0,0);row.addWidget(self.whisper_local_path);row.addWidget(browse);self._whisper_path_row=QWidget();self._whisper_path_row.setLayout(row)
        if idx>=0:self.whisper_model.setCurrentIndex(idx)
        else:self.whisper_model.setCurrentIndex(self.whisper_model.findData(None));self.whisper_local_path.setText(current_whisper)
        self.whisper_model.currentIndexChanged.connect(self._update_whisper_local_controls)
        self.whisper_status=QLabel();self.whisper_status.setWordWrap(True);self.whisper_download=QPushButton("Скачать модель");self.whisper_download.clicked.connect(self._download_selected_whisper)
        self.whisper_progress=QProgressBar();self.whisper_progress.hide();self.whisper_progress_label=QLabel();self.whisper_progress_label.hide()
        self.wake_word_enabled=QCheckBox("Включить wake word");self.wake_word_enabled.setChecked(bool(voice.get("wake_word_enabled",True)));self.wake_word=QLineEdit(voice.get("wake_word","Jarvis"))
        self.silence_duration=QDoubleSpinBox();self.silence_duration.setRange(.5,10);self.silence_duration.setSingleStep(.1);self.silence_duration.setValue(float(voice.get("silence_duration",2)))
        self.status_label=QLabel();self.status_label.setWordWrap(True)
        self.update_status=QLabel(f"Текущая версия: {APP_VERSION}");self.update_status.setWordWrap(True)
        self.update_check_button=QPushButton("Проверить обновления");self.update_check_button.clicked.connect(self._check_for_update)
        self.update_details_button=QPushButton("Открыть страницу релиза");self.update_details_button.clicked.connect(self._open_release);self.update_details_button.hide()
        update_row=QHBoxLayout();update_row.setContentsMargins(0,0,0,0);update_row.addWidget(self.update_check_button);update_row.addWidget(self.update_details_button)
        update_box=QGroupBox("Обновления");update_layout=QVBoxLayout(update_box);update_layout.addWidget(self.update_status);update_layout.addLayout(update_row)
        self._latest_release_url=""
        self.refresh_button=QPushButton("Обновить данные");self.refresh_button.clicked.connect(self.refresh_data);save=QPushButton("Сохранить настройки");save.clicked.connect(self.save)
        form=QFormLayout()
        for label,widget in [("Имя ассистента:",self.assistant_name),("Модель:",self.model),("Whisper:",self.whisper_model),("",self.whisper_status),("",self.whisper_download),("",self.whisper_progress),("",self.whisper_progress_label),("Локальная модель:",self._whisper_path_row),("Температура:",self.temperature),("Контекст:",self.context),("Максимум ответа:",self.max_tokens),("Whisper CPU-потоки:",self.whisper_cpu_threads),("Whisper Beam size:",self.whisper_beam_size),("VAD:",self.whisper_vad),("Таймкоды:",self.whisper_timestamps),("Предыдущий текст:",self.whisper_previous),("Микрофон:",self.microphone),("Wake word:",self.wake_word),("",self.wake_word_enabled),("Тишина до автоотправки:",self.silence_duration),("Ollama:",self.url),("Режим тестирования:",self.router_only_mode),("Безопасность:",self.allow_outside_workspace)]:form.addRow(label,widget)
        box=QGroupBox("Параметры");box.setLayout(form);root=QVBoxLayout(self);root.addWidget(self.status_label);root.addWidget(update_box);root.addWidget(box);root.addWidget(self.refresh_button);root.addWidget(save)
        controller.refresh_finished.connect(self._refresh_finished);controller.update_check_finished.connect(self._update_check_finished);controller.update_confirmation_requested.connect(self._update_confirmation_requested);controller.whisper_progress.connect(self._on_whisper_progress);controller.whisper_state_changed.connect(self._on_whisper_state_changed);controller.whisper_finished.connect(self._on_whisper_finished);controller.microphone_tested.connect(self._on_microphone_tested)
        self._refresh_whisper_statuses();self._load_microphones();self._set_status("Готово",False)

    def _check_for_update(self):
        if self.update_check_button.text() == "Проверка…":
            return
        self.update_check_button.setEnabled(False)
        self.update_check_button.setText("Проверка…")
        self.update_details_button.hide()
        self.update_status.setText(f"Текущая версия: {APP_VERSION}\nПроверяю GitHub Releases…")
        self.controller.check_for_update()

    def _update_confirmation_requested(self, plan):
        if self.update_check_button.isEnabled() is False:
            return
        reply = QMessageBox.question(
            self,
            "Доступно обновление",
            f"Доступна версия {plan.target_version}.\\n"
            f"Архив: {plan.asset_name}\\n"
            f"Размер: {self._format_bytes(plan.asset_size)}\\n\\n"
            "Подготовить это обновление к скачиванию?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._set_status(
                f"✓ Обновление {plan.target_version} подтверждено. "
                "Скачивание будет выполнено на следующем этапе.",
                False,
            )
        else:
            self._set_status("Обновление отложено.", False)

    def _update_check_finished(self, result):
        self.update_check_button.setEnabled(True)
        self.update_check_button.setText("Проверить обновления")
        if not result.get("success"):
            self.update_status.setText(
                f"Текущая версия: {APP_VERSION}\n⚠ {result.get('error', 'Не удалось проверить обновления')}"
            )
            return

        info = result["info"]
        self._latest_release_url = info.release_url
        if info.update_available:
            self.update_status.setText(
                f"Текущая версия: {info.current_version}\n"
                f"Доступна новая версия: {info.latest_version}\n"
                f"{info.release_name}"
            )
            self.update_details_button.setVisible(bool(info.release_url))
        else:
            message = "Релизов пока нет." if not info.tag_name else "Установлена последняя версия."
            self.update_status.setText(f"Текущая версия: {info.current_version}\n✓ {message}")

    def _open_release(self):
        if self._latest_release_url:
            webbrowser.open(self._latest_release_url)

    def _set_status(self,text,error):self.status_label.setText(text);self.status_label.setProperty("status_error",bool(error));self.status_label.style().unpolish(self.status_label);self.status_label.style().polish(self.status_label)

    def _refresh_whisper_statuses(self):
        for i,(_,name) in enumerate(self._WHISPER_PRESETS):
            if name is None:self.whisper_model.setItemText(i,"Локальная модель");continue
            status=self.controller.whisper_status(name);self.whisper_model.setItemText(i,self._WHISPER_PRESETS[i][0]+(" ✓ установлена" if status=="installed" else " • не установлена"))
        self._update_whisper_local_controls()

    def _update_whisper_local_controls(self):
        local=self.whisper_model.currentData() is None;self.whisper_local_path.setEnabled(local)
        if local:self.whisper_status.setText("Локальная модель: путь выбирается вручную.");self.whisper_download.setEnabled(False);self.whisper_progress.hide();self.whisper_progress_label.hide();return
        name=str(self.whisper_model.currentData());installed=self.controller.whisper_status(name)=="installed";self.whisper_status.setText("✓ Эта модель уже установлена." if installed else "Эта модель не установлена. Её можно скачать сейчас.");self.whisper_download.setText("Модель установлена ✓" if installed else "Скачать модель");self.whisper_download.setEnabled(not installed and not self._whisper_download_running)

    @staticmethod
    def _format_bytes(value):
        value=float(max(0,value))
        for unit in ("Б","КБ","МБ","ГБ","ТБ"):
            if value<1024 or unit=="ТБ":return f"{value:.1f} {unit}" if unit!="Б" else f"{int(value)} Б"
            value/=1024
        return f"{value:.1f} ТБ"

    @staticmethod
    def _format_eta(seconds):
        if seconds<=0:return "—"
        seconds=int(seconds);minutes,seconds=divmod(seconds,60)
        if minutes<1:return f"{seconds} с"
        hours,minutes=divmod(minutes,60)
        return f"{minutes} мин {seconds:02d} с" if hours==0 else f"{hours} ч {minutes:02d} мин"

    def _download_selected_whisper(self):
        if self._whisper_download_running:return
        name=self.whisper_model.currentData()
        if name is None:return
        self._whisper_download_running=True;self.whisper_download.setEnabled(False);self.whisper_download.setText("Загрузка…");self.whisper_progress.setValue(0);self.whisper_progress.show();self.whisper_progress_label.show();self._set_status(f"⟳ Загружаю Whisper {name}…",False);self.controller.ensure_whisper_model(str(name))

    def _on_whisper_progress(self,name,current,total,speed):
        if self.whisper_model.currentData() is None or str(self.whisper_model.currentData())!=str(name):return
        if total>0:
            percent=min(100,max(0,round(current*100/total)));eta=(total-current)/speed if speed>0 else 0;self.whisper_progress.setValue(percent);self.whisper_progress_label.setText(f"{percent}% • {self._format_bytes(current)} / {self._format_bytes(total)}\nСкорость: {self._format_bytes(speed)}/с • Осталось примерно: {self._format_eta(eta)}")
        else:self.whisper_progress_label.setText(f"{self._format_bytes(current)} скачано • определяю размер…")

    def _on_whisper_state_changed(self,name,state):
        if self.whisper_model.currentData() is None or str(self.whisper_model.currentData())!=str(name):return
        if state=="installed":self._refresh_whisper_statuses();self._set_status(f"✓ Whisper {name} установлена",False)
        elif state=="cancelled":self._set_status("Загрузка Whisper отменена",False)
        elif state=="error":self._set_status("⚠ Не удалось загрузить Whisper",True)

    def _on_whisper_finished(self,name,success,error):
        if self.whisper_model.currentData() is None or str(self.whisper_model.currentData())!=str(name):return
        self._whisper_download_running=False
        if success:self.whisper_progress.setValue(100);self.whisper_progress_label.setText("100% • модель полностью загружена")
        else:self.whisper_progress_label.setText(f"Ошибка: {error or 'неизвестная ошибка'}")
        self._refresh_whisper_statuses();self._update_whisper_local_controls()

    def _choose_whisper_model(self):
        directory=QFileDialog.getExistingDirectory(self,"Выберите папку локальной Whisper-модели",self.whisper_local_path.text().strip() or str(Path.home()))
        if directory:self.whisper_local_path.setText(directory)

    def _load_microphones(self):
        result=self.controller.list_microphones();self._apply_microphones(result)

    def _apply_microphones(self,result):
        self.microphone.blockSignals(True);self.microphone.clear()
        if not result.get("success"):self.microphone.addItem("Не удалось получить список микрофонов");self.microphone.setToolTip(result.get("error",""))
        else:
            for item in result["devices"]:
                self.microphone.addItem(item["name"],item["index"])
                if item.get("hostapi_name"):self.microphone.setItemData(self.microphone.count()-1,f"Устройство ввода через {item['hostapi_name']} (индекс {item['index']})",3)
                if item.get("selected"):self.microphone.setCurrentIndex(self.microphone.count()-1)
        self.microphone.blockSignals(False)

    def refresh_data(self):
        if self._refresh_running:return
        self._refresh_running=True;self.refresh_button.setEnabled(False);self._set_status("⟳ Обновляю данные…",False);self.controller.refresh()

    def _refresh_finished(self,result):
        if "models" not in result:return
        self._refresh_running=False;self.refresh_button.setEnabled(True)
        if result.get("success") is False:self._set_status("⚠ "+result.get("error","неизвестная ошибка"),True);return
        current=self.model.currentText();self.model.clear();self.model.addItems(result.get("models",[]));self.model.setCurrentText(current);self._apply_microphones(result.get("microphones",{}));self._refresh_whisper_statuses();self._set_status("✓ Данные обновлены",False)

    def save(self):
        whisper=self.whisper_model.currentData() if self.whisper_model.currentData() is not None else self.whisper_local_path.text().strip()
        if not whisper:QMessageBox.warning(self,"Настройки Whisper","Для локальной модели нужно указать папку с моделью.");return
        if self.whisper_model.currentData() is None and not Path(whisper).expanduser().is_dir():QMessageBox.warning(self,"Настройки Whisper",f"Папка локальной модели не найдена:\n{Path(whisper).expanduser()}");return
        device=self.microphone.currentData();values={"assistant_name":self.assistant_name.text().strip() or "JARVIS","model":self.model.currentText().strip(),"temperature":self.temperature.value(),"context_length":self.context.value(),"max_tokens":self.max_tokens.value(),"router_only_mode":self.router_only_mode.isChecked(),"allow_outside_workspace":self.allow_outside_workspace.isChecked(),"ollama_url":self.url.text().strip().rstrip("/"),"voice":{"model":str(whisper),"input_device":device,"input_device_name":self.microphone.currentText().strip() if device is not None else None,"wake_word_enabled":self.wake_word_enabled.isChecked(),"wake_word":self.wake_word.text().strip() or "Jarvis","silence_duration":self.silence_duration.value(),"cpu_threads":self.whisper_cpu_threads.value(),"beam_size":self.whisper_beam_size.value(),"vad_filter":self.whisper_vad.isChecked(),"without_timestamps":not self.whisper_timestamps.isChecked(),"condition_on_previous_text":self.whisper_previous.isChecked()}}
        model,name=self.controller.save(values);self.settings_changed.emit(model,name);self._set_status("✓ Настройки сохранены",False)

    def _on_microphone_tested(self,result):pass
