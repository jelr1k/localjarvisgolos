from __future__ import annotations

import re

MAX_SPEECH_CHARS = 16000
SPEECH_CHUNK_CHARS = 420

def prepare_speech_text(value: str) -> str:
    """Remove common Markdown and code noise before sending text to TTS."""
    text = str(value or "")
    text = re.sub(r"\x60{3}.*?\x60{3}", " ", text, flags=re.DOTALL)
    text = re.sub(r"~~~.*?~~~", " ", text, flags=re.DOTALL)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\((?:[^()]|\([^()]*\))*\)", r"\1", text)
    text = re.sub(r"\x60[^\x60]*\x60", " ", text)
    text = re.sub(r"https?://\S+", " ссылка ", text)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", text)
    text = re.sub(r"[*_~]{1,3}", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > MAX_SPEECH_CHARS:
        text = text[:MAX_SPEECH_CHARS].rsplit(" ", 1)[0].rstrip() + ". Остальная часть ответа не озвучена."
    return text


def split_speech_text(value: str, max_chars: int = SPEECH_CHUNK_CHARS) -> list[str]:
    """Split long answers near sentence boundaries so playback can start early."""
    text = prepare_speech_text(value)
    max_chars = max(80, int(max_chars))
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?…])\s+|\n+", text)
    chunks: list[str] = []
    current = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        while len(sentence) > max_chars:
            cut = sentence.rfind(" ", 0, max_chars + 1)
            if cut < 1:
                cut = max_chars
            part, sentence = sentence[:cut].strip(), sentence[cut:].strip()
            if current:
                chunks.append(current)
                current = ""
            if part:
                chunks.append(part)
        if not sentence:
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks
