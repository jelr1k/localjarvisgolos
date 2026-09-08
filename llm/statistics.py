def ns_to_s(value):
    return (value or 0) / 1_000_000_000

def calculate_stats(final_response: dict, elapsed_to_first_token: float | None, thinking: bool):
    total = ns_to_s(final_response.get("total_duration"))
    load = ns_to_s(final_response.get("load_duration"))
    prompt_eval = ns_to_s(final_response.get("prompt_eval_duration"))
    eval_time = ns_to_s(final_response.get("eval_duration"))
    output_tokens = final_response.get("eval_count", 0) or 0
    input_tokens = final_response.get("prompt_eval_count", 0) or 0

    speed = output_tokens / eval_time if eval_time > 0 else 0.0

    return {
        "model": final_response.get("model", ""),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "generation_time_s": eval_time,
        "generation_speed_tps": speed,
        "total_time_s": total,
        "load_time_s": load,
        "prompt_eval_time_s": prompt_eval,
        "eval_time_s": eval_time,
        "ttft_s": elapsed_to_first_token or 0.0,
        "thinking": thinking,
    }
