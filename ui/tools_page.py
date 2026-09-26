from __future__ import annotations
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox,QGroupBox,QLabel,QVBoxLayout,QWidget
from tools.paths import TOOL_WORKSPACE

class ToolsPage(QWidget):
    tools_changed=Signal()
    def __init__(self,controller):
        super().__init__();self.controller=controller;self.checkboxes={}
        title=QLabel("Инструменты Jarvis");title.setStyleSheet("font-size:18px;font-weight:bold;")
        box=QGroupBox("Доступные инструменты");layout=QVBoxLayout(box)
        names={"search_files":"Поиск файлов","read_file":"Чтение файла","create_file":"Создание файла","write_file":"Запись файла","delete_file":"Удаление файла","rename_file":"Переименование файла","copy_file":"Копирование файла","move_file":"Перемещение файла","create_folder":"Создание папки","file_info":"Информация о файле","find_application":"Поиск приложения","get_process_status":"Проверка состояния приложения","launch_application":"Запуск приложения","minimize_application":"Сворачивание приложения","close_application":"Закрытие приложения","open_url":"Открытие ссылки"}
        for name,tool in controller.tools().items():
            cb=QCheckBox(names.get(name,name));cb.setChecked(controller.is_enabled(name));cb.setToolTip(tool.get("description",""));cb.toggled.connect(lambda value,n=name:self._set_tool(n,value));self.checkboxes[name]=cb;layout.addWidget(cb)
        hint=QLabel("Отключённый инструмент одновременно убирается из доступных модели и блокируется повторной проверкой при выполнении. Все файловые инструменты ограничены workspace.");hint.setWordWrap(True)
        root=QVBoxLayout(self);root.addWidget(title);root.addWidget(QLabel(f"Рабочая папка: {TOOL_WORKSPACE}"));root.addWidget(box);root.addWidget(hint);root.addStretch()
    def _set_tool(self,name,enabled):self.controller.set_enabled(name,enabled);self.tools_changed.emit()
