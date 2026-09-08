from dataclasses import dataclass, field

@dataclass
class ChatRequest:
    model: str
    messages: list[dict]
    thinking: bool = False
    temperature: float = 0.7
    context_length: int = 32768
    max_tokens: int = 4096
