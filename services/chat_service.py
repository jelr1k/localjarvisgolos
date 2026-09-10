from PySide6.QtCore import QObject, Signal, QThread

from chat.conversation import Conversation
from llm.request import ChatRequest


class GenerationWorker(QObject):
    chunk = Signal(object)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, provider, request):
        super().__init__()

        self.provider = provider
        self.request = request

    def run(self):
        try:
            for item in self.provider.stream_chat(
                self.request
            ):
                # Отправляем обычные chunks
                if not item.done:
                    self.chunk.emit(item)
                    continue

                # Сначала заканчиваем поток,
                # затем отдельно отправляем finished.
                self.finished.emit(item.stats)

        except Exception as exc:
            self.failed.emit(str(exc))


class ChatService(QObject):
    chunk_received = Signal(object)
    generation_finished = Signal(object)
    error = Signal(str)

    def __init__(self, provider, config):
        super().__init__()

        self.provider = provider
        self.config = config

        self.conversation = Conversation()

        self._thread = None
        self._worker = None

        self._current_answer = ""

    def send(self, text):
        if (
            self._thread
            and self._thread.isRunning()
        ):
            return

        text = text.strip()

        if not text:
            return

        self.conversation.add(
            "user",
            text
        )

        self._current_answer = ""

        request = ChatRequest(
            model=self.config.get("model"),
            messages=(
                self.conversation
                .as_ollama_messages()
            ),
            thinking=self.config.get(
                "thinking"
            ),
            temperature=float(
                self.config.get("temperature")
            ),
            context_length=int(
                self.config.get("context_length")
            ),
            max_tokens=int(
                self.config.get("max_tokens")
            ),
        )

        self._thread = QThread()

        self._worker = GenerationWorker(
            self.provider,
            request
        )

        self._worker.moveToThread(
            self._thread
        )

        self._thread.started.connect(
            self._worker.run
        )

        self._worker.chunk.connect(
            self._on_chunk
        )

        self._worker.finished.connect(
            self._on_finished
        )

        self._worker.failed.connect(
            self._on_failed
        )

        self._worker.finished.connect(
            self._thread.quit
        )

        self._worker.failed.connect(
            self._thread.quit
        )

        self._thread.finished.connect(
            self._cleanup
        )

        self._thread.start()

    def _on_chunk(self, chunk):
        """
        Получает потоковые chunks от worker.

        Этот метод выполняется в GUI-потоке,
        поэтому здесь нельзя делать тяжёлые операции.
        """

        if chunk.text:
            self._current_answer += chunk.text

        # Передаём chunk дальше в ChatPage.
        #
        # ChatPage сама буферизует текст и обновляет GUI
        # с ограниченной частотой.
        self.chunk_received.emit(chunk)

    def _on_finished(self, stats):
        # Сохраняем только обычный ответ.
        #
        # Thinking в историю разговора не добавляем.
        if self._current_answer.strip():
            self.conversation.add(
                "assistant",
                self._current_answer
            )

        self.generation_finished.emit(
            stats
        )

    def _on_failed(self, error):
        self.error.emit(error)

    def _cleanup(self):
        if self._worker:
            self._worker.deleteLater()

        if self._thread:
            self._thread.deleteLater()

        self._worker = None
        self._thread = None

    def add_assistant_message(self, text):
        if text and text.strip():
            self.conversation.add(
                "assistant",
                text
            )