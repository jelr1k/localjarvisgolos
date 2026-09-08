from dataclasses import dataclass, field
from chat.message import Message

@dataclass
class Conversation:
    messages: list[Message] = field(default_factory=list)

    def add(self, role, content):
        self.messages.append(Message(role, content))

    def as_ollama_messages(self):
        return [{"role": m.role, "content": m.content} for m in self.messages]
