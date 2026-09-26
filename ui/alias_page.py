from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QListWidget,QListWidgetItem,QMessageBox,QPushButton,QTextEdit,QVBoxLayout,QWidget

CATEGORY_LABELS={"applications":"Приложение","files":"Файл"}

class AliasPage(QWidget):
    def __init__(self, controller):
        super().__init__(); self.controller=controller; self._editing_key=None
        title=QLabel("Алиасы"); title.setStyleSheet("font-size:18px;font-weight:bold;")
        hint=QLabel("Здесь можно задать несколько названий одному приложению или файлу. Workspace является основной точкой добавления файлов."); hint.setWordWrap(True)
        self.items=QListWidget(); self.items.currentItemChanged.connect(self._load_selected)
        self.category=QComboBox(); self.category.addItem("Приложение","applications"); self.category.addItem("Файл","files"); self.category.currentIndexChanged.connect(self._category_changed)
        self.target=QLineEdit(); self.aliases=QTextEdit(); self.aliases.setPlaceholderText("По одному алиасу на строку"); self.aliases.setMinimumHeight(150)
        form=QFormLayout(); form.addRow("Тип:",self.category); form.addRow("Реальное имя / путь:",self.target); form.addRow("Названия:",self.aliases)
        self.new_button=QPushButton("Новый"); self.save_button=QPushButton("Сохранить"); self.delete_button=QPushButton("Удалить"); self.reset_button=QPushButton("Сбросить")
        self.new_button.clicked.connect(self._new); self.save_button.clicked.connect(self._save); self.delete_button.clicked.connect(self._delete); self.reset_button.clicked.connect(self._clear_form)
        buttons=QHBoxLayout(); [buttons.addWidget(b) for b in (self.new_button,self.save_button,self.delete_button,self.reset_button)]
        editor=QVBoxLayout(); editor.addWidget(QLabel("Редактор")); editor.addLayout(form); editor.addLayout(buttons); editor.addStretch()
        content=QHBoxLayout(); content.addWidget(self.items,1); ew=QWidget(); ew.setLayout(editor); content.addWidget(ew,2)
        root=QVBoxLayout(self); root.addWidget(title); root.addWidget(hint); root.addLayout(content)
        self.refresh(); self._new()
    def refresh(self):
        current=self._editing_key; self.items.blockSignals(True); self.items.clear()
        for entry in self.controller.list_objects():
            if entry["category"] not in {"applications","files"}: continue
            item=QListWidgetItem(f"[{CATEGORY_LABELS.get(entry['category'],entry['category'])}] {entry['target']}"); item.setData(Qt.ItemDataRole.UserRole,(entry["category"],entry["target"])); self.items.addItem(item)
        self.items.blockSignals(False)
        if current:self._select_key(current)
    def _category_changed(self):
        self.target.setPlaceholderText("Например: Discord или Prism Launcher" if self.category.currentData()=="applications" else "Имя или путь относительно workspace")
    def _load_selected(self,current,previous=None):
        if current is None:return
        key=current.data(Qt.ItemDataRole.UserRole)
        if not key:return
        category,target=key; self._editing_key=key; index=self.category.findData(category)
        if index>=0:self.category.blockSignals(True); self.category.setCurrentIndex(index); self.category.blockSignals(False); self._category_changed()
        self.target.setText(target); self.aliases.setPlainText("\n".join(self.controller.get_aliases(category,target)))
    def _new(self):self._editing_key=None;self.items.clearSelection();self._clear_form()
    def _clear_form(self):self.target.clear();self.aliases.clear();self._category_changed();self.target.setFocus()
    def _save(self):
        category=self.category.currentData();target=self.target.text().strip();aliases=[x.strip() for x in self.aliases.toPlainText().splitlines() if x.strip()]
        if not target:QMessageBox.warning(self,"Алиасы","Укажи реальное имя или путь объекта.");return
        if not aliases:aliases=self.controller.default_aliases(category,target)
        old=self._editing_key
        try:self.controller.set_aliases(category,target,aliases)
        except self.controller.alias_error_type() as exc:QMessageBox.warning(self,"Алиасы",str(exc));return
        except OSError as exc:QMessageBox.critical(self,"Алиасы",f"Не удалось сохранить aliases.json: {exc}");return
        if old and old!=(category,target):
            try:self.controller.remove_object(*old)
            except OSError as exc:QMessageBox.critical(self,"Алиасы",f"Новая запись сохранена, но старую запись не удалось удалить: {exc}");return
        self._editing_key=(category,target);self.refresh();self._select_key(self._editing_key)
    def _select_key(self,key):
        for row in range(self.items.count()):
            item=self.items.item(row)
            if item.data(Qt.ItemDataRole.UserRole)==key:self.items.setCurrentItem(item);break
    def _delete(self):
        if not self._editing_key:return
        category,target=self._editing_key
        if QMessageBox.question(self,"Удалить алиасы",f"Удалить запись «{target}» и все её алиасы?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)!=QMessageBox.StandardButton.Yes:return
        try:self.controller.remove_object(category,target)
        except OSError as exc:QMessageBox.critical(self,"Алиасы",f"Не удалось сохранить aliases.json: {exc}");return
        self.refresh();self._new()
