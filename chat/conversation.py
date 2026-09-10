from dataclasses import dataclass, field
from chat.message import Message


@dataclass
class Conversation:
    messages: list[Message] = field(default_factory=list)

    def add(self, role, content):
        self.messages.append(Message(role, content))

    def add_ollama_message(self, message: dict):
        """Добавляет служебное сообщение Ollama."""
        item = Message(
            message.get("role", "assistant"),
            message.get("content", ""),
        )
        setattr(
            item,
            "_ollama_extra",
            {
                key: value
                for key, value in message.items()
                if key not in {"role", "content"}
            },
        )
        self.messages.append(item)

    def as_ollama_messages(self):
        result = []
        for message in self.messages:
            item = {
                "role": message.role,
                "content": message.content,
            }
            item.update(getattr(message, "_ollama_extra", {}))
            result.append(item)
        return result
