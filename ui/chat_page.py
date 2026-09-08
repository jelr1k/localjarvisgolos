from PySide6.QtCore import Signal, QEvent, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
)


class ChatPage(QWidget):
    send_requested = Signal(str)

    def __init__(self, chat_service, config):
        super().__init__()

        self.chat_service = chat_service
        self.config = config

        self.answer = ""
        self.thinking = ""

        # Имя ассистента из настроек
        self.assistant_name = config.get(
            "assistant_name",
            "JARVIS"
        )

        self.model_label = QLabel()

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)

        self.input = QTextEdit()
        self.input.setPlaceholderText(
            "Введите сообщение..."
        )
        self.input.setFixedHeight(90)

        self.send_button = QPushButton("Отправить")
        self.send_button.clicked.connect(self.send)

        bottom = QHBoxLayout()
        bottom.addWidget(self.input)
        bottom.addWidget(self.send_button)

        layout = QVBoxLayout(self)

        layout.addWidget(self.model_label)
        layout.addWidget(self.chat)
        layout.addLayout(bottom)

        self.input.installEventFilter(self)

    def update_model_label(self, model):
        self.model_label.setText(
            f"Модель: {model}"
        )

    def update_assistant_name(self, name):
        self.assistant_name = (
            name.strip() or "JARVIS"
        )

    def update_settings(self, model, assistant_name):
        self.update_model_label(model)
        self.update_assistant_name(assistant_name)

    def eventFilter(self, obj, event):
        if (
            obj is self.input
            and event.type() == QEvent.Type.KeyPress
        ):
            if event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            ):
                # Shift + Enter = новая строка
                if (
                    event.modifiers()
                    & Qt.KeyboardModifier.ShiftModifier
                ):
                    return False

                # Enter = отправка
                self.send()
                return True

        return super().eventFilter(obj, event)

    def send(self):
        text = self.input.toPlainText().strip()

        if not text:
            return

        self.chat.append(
            f"<b>Ты:</b> {text}"
        )

        self.input.clear()

        self.answer = ""
        self.thinking = ""

        self.send_button.setEnabled(False)

        self.send_requested.emit(text)

    def on_chunk(self, chunk):
        if chunk.thinking:
            self.thinking += chunk.thinking

        if not chunk.text:
            return

        if not self.answer:
            self.chat.append(
                f"<b>{self.assistant_name}:</b>"
            )

        self.answer += chunk.text

        cursor = self.chat.textCursor()

        cursor.movePosition(
            cursor.MoveOperation.End
        )

        self.chat.setTextCursor(cursor)

        self.chat.insertPlainText(
            chunk.text
        )

        self.chat.ensureCursorVisible()

    def finish_generation(self):
        if self.answer:
            self.chat.append("")

        self.send_button.setEnabled(True)
        self.input.setFocus()
