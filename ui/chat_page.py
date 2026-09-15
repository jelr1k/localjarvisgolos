from PySide6.QtCore import Signal, QEvent, Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QPushButton


class ChatPage(QWidget):
    send_requested = Signal(str)

    def __init__(self, chat_service, config):
        super().__init__()
        self.chat_service = chat_service
        self.config = config
        self.answer = ""
        self.thinking = ""
        self.pending_answer = ""
        self.pending_thinking = ""
        self.thinking_started = False
        self.answer_started = False
        self.assistant_name = config.get("assistant_name", "JARVIS")
        self.model_label = QLabel()
        self.voice_status = QLabel("Голос: готов")
        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.input = QTextEdit()
        self.input.setPlaceholderText("Введите сообщение…")
        self.input.setFixedHeight(90)
        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send)
        self.voice_button = QPushButton("🎙 Зажать и говорить")
        self.voice_button.setToolTip("Зажми кнопку, скажи команду и отпусти")
        self.voice_button.pressed.connect(self._voice_pressed)
        self.voice_button.released.connect(self._voice_released)

        bottom = QHBoxLayout()
        bottom.addWidget(self.input)
        bottom.addWidget(self.send_button)
        bottom.addWidget(self.voice_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.model_label)
        layout.addWidget(self.voice_status)
        layout.addWidget(self.chat)
        layout.addLayout(bottom)
        self.input.installEventFilter(self)

        self.stream_timer = QTimer(self)
        self.stream_timer.timeout.connect(self.flush_stream)
        self.stream_timer.start(33)
        self.voice_controller = None

    def set_voice_controller(self, controller):
        self.voice_controller = controller
        controller.listening_changed.connect(self.on_voice_listening_changed)
        controller.transcribing_changed.connect(self.on_voice_transcribing_changed)
        controller.transcript_ready.connect(self.on_voice_transcript)
        controller.error.connect(self.on_voice_error)

    def update_model_label(self, model):
        self.model_label.setText(f"Модель: {model}")

    def update_assistant_name(self, name):
        self.assistant_name = name.strip() or "JARVIS"

    def update_settings(self, model, assistant_name):
        self.update_model_label(model)
        self.update_assistant_name(assistant_name)

    def eventFilter(self, obj, event):
        if obj is self.input and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                    return False
                self.send()
                return True
        return super().eventFilter(obj, event)

    def _voice_pressed(self):
        if self.voice_controller is not None:
            self.voice_controller.start()

    def _voice_released(self):
        if self.voice_controller is not None:
            self.voice_controller.stop()

    def send(self):
        self._send_text(self.input.toPlainText().strip())
        self.input.clear()

    def send_voice_text(self, text):
        self._send_text(text, clear_input=False)

    def _send_text(self, text, clear_input=True):
        text = text.strip()
        if not text:
            return
        self.chat.append(f"<b>Ты:</b> {text}")
        if clear_input:
            self.input.clear()
        self.answer = self.thinking = ""
        self.pending_answer = self.pending_thinking = ""
        self.thinking_started = self.answer_started = False
        self.send_button.setEnabled(False)
        self.send_requested.emit(text)

    def on_voice_listening_changed(self, listening):
        if listening:
            self.voice_status.setText("Голос: 🔴 слушаю…")
            self.voice_button.setText("🎙 Отпустить — распознать")
        else:
            self.voice_status.setText("Голос: обрабатываю…")
            self.voice_button.setText("🎙 Зажать и говорить")

    def on_voice_transcribing_changed(self, transcribing):
        if transcribing:
            self.voice_status.setText("Голос: ⏳ распознаю…")
            self.voice_button.setEnabled(False)
        else:
            self.voice_button.setEnabled(True)
            if self.voice_status.text().startswith("Голос: ⏳"):
                self.voice_status.setText("Голос: готов")

    def on_voice_transcript(self, text):
        self.voice_status.setText(f"Голос: «{text}»")
        self.send_voice_text(text)

    def on_voice_error(self, error):
        self.voice_status.setText("Голос: ошибка")
        self.voice_button.setEnabled(True)
        self.chat.append(f"<b>{self.assistant_name}:</b> {error}")

    def on_direct_response(self, text):
        self.chat.append(f"<b>{self.assistant_name}:</b> {text}")
        self.send_button.setEnabled(True)
        self.input.setFocus()

    def on_chunk(self, chunk):
        if chunk.thinking:
            self.thinking += chunk.thinking
            self.pending_thinking += chunk.thinking
        if chunk.text:
            self.answer += chunk.text
            self.pending_answer += chunk.text

    def flush_stream(self):
        if not self.pending_thinking and not self.pending_answer:
            return
        cursor = self.chat.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if self.pending_thinking:
            if not self.thinking_started:
                self.chat.append(f"<b>{self.assistant_name}:</b>")
                cursor = self.chat.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                cursor.insertHtml("<br><i>Раздумья:</i><br>")
                self.thinking_started = True
            cursor = self.chat.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(self.pending_thinking)
            self.pending_thinking = ""

        if self.pending_answer:
            if not self.answer_started:
                cursor = self.chat.textCursor()
                cursor.movePosition(cursor.MoveOperation.End)
                if self.thinking_started:
                    cursor.insertHtml("<br><br><b>Ответ:</b><br>")
                else:
                    self.chat.append(f"<b>{self.assistant_name}:</b>")
                self.answer_started = True
            cursor = self.chat.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            cursor.insertText(self.pending_answer)
            self.pending_answer = ""
        self.chat.ensureCursorVisible()

    def finish_generation(self):
        self.flush_stream()
        self.send_button.setEnabled(True)
        if self.voice_controller is None or not self.voice_controller.transcribing():
            self.voice_status.setText("Голос: готов")
        self.input.setFocus()
