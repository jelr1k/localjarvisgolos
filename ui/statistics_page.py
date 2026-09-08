import psutil

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QGroupBox,
    QFormLayout,
)

from core.ollama_manager import OllamaManager


class StatisticsPage(QWidget):
    def __init__(self, service, ollama_manager):
        super().__init__()

        self.service = service
        self.ollama_manager = ollama_manager

        self.labels = {}

        # =========================
        # Последний запрос
        # =========================

        form = QFormLayout()

        fields = [
            ("model", "Модель"),
            ("input_tokens", "Входных токенов"),
            ("output_tokens", "Выходных токенов"),
            ("total_tokens", "Всего токенов"),
            ("generation_time_s", "Время генерации"),
            ("generation_speed_tps", "Скорость генерации"),
            ("total_time_s", "Общее время"),
            ("load_time_s", "Загрузка модели"),
            ("prompt_eval_time_s", "Обработка промпта"),
            ("ttft_s", "TTFT"),
            ("thinking", "Раздумывания"),
        ]

        for key, name in fields:
            label = QLabel("—")
            self.labels[key] = label
            form.addRow(name + ":", label)

        box = QGroupBox("Последний запрос")
        box.setLayout(form)

        # =========================
        # Состояние системы
        # =========================

        system_form = QFormLayout()

        system_fields = [
            ("processor", "Модель работает на"),
            ("gpu_memory", "Память GPU"),
            ("model_memory", "Память модели"),
            ("ram_usage", "ОЗУ"),
            ("cpu_usage", "Загрузка CPU"),
        ]

        for key, name in system_fields:
            label = QLabel("—")
            self.labels[key] = label
            system_form.addRow(name + ":", label)

        system_box = QGroupBox("Состояние системы")
        system_box.setLayout(system_form)

        # =========================
        # Layout
        # =========================

        layout = QVBoxLayout(self)

        layout.addWidget(box)
        layout.addWidget(system_box)
        layout.addStretch()

        # Обновляем состояние каждую секунду
        self.monitor_timer = QTimer(self)
        self.monitor_timer.timeout.connect(self.update_system_status)
        self.monitor_timer.start(1000)

        self.update_system_status()

    def refresh(self, stats):
        if not stats:
            return

        self.labels["model"].setText(stats.model)
        self.labels["input_tokens"].setText(str(stats.input_tokens))
        self.labels["output_tokens"].setText(str(stats.output_tokens))
        self.labels["total_tokens"].setText(str(stats.total_tokens))

        self.labels["generation_time_s"].setText(
            f"{stats.generation_time_s:.3f} с"
        )

        self.labels["generation_speed_tps"].setText(
            f"{stats.generation_speed_tps:.2f} ток/с"
        )

        self.labels["total_time_s"].setText(
            f"{stats.total_time_s:.3f} с"
        )

        self.labels["load_time_s"].setText(
            f"{stats.load_time_s:.3f} с"
        )

        self.labels["prompt_eval_time_s"].setText(
            f"{stats.prompt_eval_time_s:.3f} с"
        )

        self.labels["ttft_s"].setText(
            f"{stats.ttft_s:.3f} с"
        )

        self.labels["thinking"].setText(
            "ВКЛ" if stats.thinking else "ВЫКЛ"
        )

    def update_system_status(self):
        # =========================
        # CPU / RAM
        # =========================

        cpu = psutil.cpu_percent(interval=None)
        ram = psutil.virtual_memory()

        self.labels["cpu_usage"].setText(
            f"{cpu:.0f}%"
        )

        self.labels["ram_usage"].setText(
            f"{ram.used / 1024**3:.1f} / "
            f"{ram.total / 1024**3:.1f} ГБ "
            f"({ram.percent:.0f}%)"
        )

        # =========================
        # Ollama
        # =========================

        model = self.labels["model"].text()

        if not model or model == "—":
            return

        status = self.ollama_manager.get_model_status(model)

        if not status:
            self.labels["processor"].setText("Модель не загружена")
            self.labels["gpu_memory"].setText("—")
            self.labels["model_memory"].setText("—")
            return

        # =========================
        # CPU / GPU placement
        # =========================

        processor = status.get("processor")

        if processor:
            self.labels["processor"].setText(
                processor
            )
        else:
            # На случай версии Ollama без processor
            size = status.get("size", 0)
            size_vram = status.get("size_vram", 0)

            if size:
                gpu_percent = (
                    size_vram / size * 100
                )

                cpu_percent = 100 - gpu_percent

                self.labels["processor"].setText(
                    f"{cpu_percent:.0f}% CPU / "
                    f"{gpu_percent:.0f}% GPU"
                )

        # =========================
        # VRAM
        # =========================

        size_vram = status.get("size_vram", 0)

        if size_vram:
            self.labels["gpu_memory"].setText(
                f"{size_vram / 1024**3:.2f} ГБ"
            )
        else:
            self.labels["gpu_memory"].setText(
                "0 ГБ"
            )

        # =========================
        # Общая память модели
        # =========================

        size = status.get("size", 0)

        if size:
            self.labels["model_memory"].setText(
                f"{size / 1024**3:.2f} ГБ"
            )
        else:
            self.labels["model_memory"].setText("—")
