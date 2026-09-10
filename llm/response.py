from dataclasses import dataclass, field


@dataclass
class GenerationStats:
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    generation_time_s: float = 0.0
    generation_speed_tps: float = 0.0
    total_time_s: float = 0.0
    load_time_s: float = 0.0
    prompt_eval_time_s: float = 0.0
    eval_time_s: float = 0.0
    ttft_s: float = 0.0
    thinking: bool = False


@dataclass
class StreamChunk:
    text: str = ""
    thinking: str = ""
    tool_calls: list[dict] = field(default_factory=list)
    done: bool = False
    stats: GenerationStats | None = None
    raw: dict = field(default_factory=dict)
