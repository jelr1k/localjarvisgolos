from __future__ import annotations
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget,QVBoxLayout,QLabel,QGroupBox,QFormLayout

class StatisticsPage(QWidget):
    def __init__(self,controller):
        super().__init__();self.controller=controller;self.monitor_busy=False;self.labels={}
        form=QFormLayout();fields=[("model","Модель"),("input_tokens","Входных токенов"),("output_tokens","Выходных токенов"),("total_tokens","Всего токенов"),("generation_time_s","Время генерации"),("generation_speed_tps","Скорость генерации"),("total_time_s","Общее время"),("load_time_s","Загрузка модели"),("prompt_eval_time_s","Обработка промпта"),("ttft_s","TTFT"),("thinking","Раздумывания")]
        for key,name in fields:self.labels[key]=QLabel("—");form.addRow(name+":",self.labels[key])
        box=QGroupBox("Последний запрос");box.setLayout(form)
        sf=QFormLayout()
        for key,name in [("processor","Модель работает на"),("gpu_memory","Память GPU"),("model_memory","Память модели"),("ram_usage","ОЗУ"),("cpu_usage","Загрузка CPU")]:self.labels[key]=QLabel("—");sf.addRow(name+":",self.labels[key])
        sb=QGroupBox("Состояние системы");sb.setLayout(sf)

        wf=QFormLayout()
        for key,name in [
            ("whisper_model","Модель"),
            ("whisper_beam","Beam size"),
            ("whisper_load","Загрузка модели"),
            ("whisper_transcription","Распознавание"),
            ("whisper_audio","Длительность аудио"),
            ("whisper_rtf","Real-time factor"),
            ("whisper_unload","Выгрузка модели"),
            ("whisper_threads","CPU-потоки"),
        ]:
            self.labels[key]=QLabel("—");wf.addRow(name+":",self.labels[key])
        wb=QGroupBox("Whisper");wb.setLayout(wf)

        root=QVBoxLayout(self);root.addWidget(box);root.addWidget(wb);root.addWidget(sb);root.addStretch()
        self.timer=QTimer(self);self.timer.timeout.connect(self.update_system_status);self.timer.start(1000)
        self.controller.system_status.connect(self.on_system_status)
        self.controller.whisper_updated.connect(self.on_whisper_updated)
    def refresh(self,stats):
        if not stats:return
        for key,value in [("model",stats.model),("input_tokens",stats.input_tokens),("output_tokens",stats.output_tokens),("total_tokens",stats.total_tokens),("generation_time_s",f"{stats.generation_time_s:.3f} с"),("generation_speed_tps",f"{stats.generation_speed_tps:.2f} ток/с"),("total_time_s",f"{stats.total_time_s:.3f} с"),("load_time_s",f"{stats.load_time_s:.3f} с"),("prompt_eval_time_s",f"{stats.prompt_eval_time_s:.3f} с"),("ttft_s",f"{stats.ttft_s:.3f} с"),("thinking","ВКЛ" if stats.thinking else "ВЫКЛ")]:self.labels[key].setText(str(value))
        self.update_system_status()
    def on_whisper_updated(self,stats):
        self.labels["whisper_model"].setText(str(stats.model))
        self.labels["whisper_beam"].setText(str(stats.beam_size))
        self.labels["whisper_load"].setText(f"{stats.load_time_s:.3f} с" if stats.load_time_s > 0 else "Уже загружена")
        self.labels["whisper_transcription"].setText(f"{stats.transcription_time_s:.3f} с")
        self.labels["whisper_audio"].setText(f"{stats.audio_duration_s:.3f} с")
        self.labels["whisper_rtf"].setText(f"{stats.real_time_factor:.3f}")
        self.labels["whisper_unload"].setText(
            f"{stats.unload_time_s:.3f} с" if stats.unload_time_s is not None else "Не выгружается"
        )
        self.labels["whisper_threads"].setText(str(stats.cpu_threads))

    def update_system_status(self):
        if self.monitor_busy:return
        model=self.labels["model"].text()
        if not model or model=="—":return
        self.monitor_busy=True;self.controller.update_system_status(model)
    def on_system_status(self,result):
        self.monitor_busy=False;status=result.get("status");cpu=result.get("cpu",0);ram_used=result.get("ram_used",0);ram_total=result.get("ram_total",0);ram_percent=result.get("ram_percent",0)
        self.labels["cpu_usage"].setText(f"{cpu:.0f}%")
        if ram_total:self.labels["ram_usage"].setText(f"{ram_used/1024**3:.1f} / {ram_total/1024**3:.1f} ГБ ({ram_percent:.0f}%)")
        if not status:
            self.labels["processor"].setText("Модель не загружена");self.labels["gpu_memory"].setText("—");self.labels["model_memory"].setText("—");return
        processor=status.get("processor");size=status.get("size",0);vram=status.get("size_vram",0)
        if processor:self.labels["processor"].setText(processor)
        elif size:self.labels["processor"].setText(f"{100-vram/size*100:.0f}% CPU / {vram/size*100:.0f}% GPU")
        else:self.labels["processor"].setText("—")
        self.labels["gpu_memory"].setText(f"{vram/1024**3:.2f} ГБ" if vram else "0 ГБ")
        self.labels["model_memory"].setText(f"{size/1024**3:.2f} ГБ" if size else "—")
