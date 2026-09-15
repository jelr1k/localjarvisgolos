from __future__ import annotations

import re
import unicodedata


# Conservative mappings for words Whisper commonly produces when a user speaks
# punctuation or a file extension aloud in Russian. Keep this list intentionally
# small: the normalizer must not silently rewrite ordinary user text.
_SPOKEN_PUNCTUATION = (
    (r"\bнижн(?:ее|яя)\s+подч[её]ркивание\b", "_"),
    (r"\bнижн(?:ее|яя)\s+подчеркивание\b", "_"),
    (r"\bподч[её]ркивание\b", "_"),
    (r"\bподчеркивание\b", "_"),
    (r"\bточк(?:а|у|ой)\b", "."),
    (r"\bсл[её]ш\b", "/"),
    (r"\bслэш\b", "/"),
    (r"\bобратн(?:ый|ая)\s+слэш\b", "\\"),
    (r"\bдефис\b", "-"),
    (r"\bтире\b", "-"),
)

# Variants that frequently appear as a single word or phonetic rendering of a
# spoken extension. The replacement is only made when it follows a dot, so
# ordinary words such as "текст" are not changed globally.
_EXTENSION_ALIASES = {
    "тхт": "txt",
    "текстей": "txt",
    "тексти": "txt",
    "текст": "txt",
    "тэикст": "txt",
    "пи": "py",
    "пайтон": "py",
    "джейсон": "json",
    "джсон": "json",
    "джей сон": "json",
    "эмдэ": "md",
    "эм ди": "md",
    "эс вэ": "csv",
    "сиэсви": "csv",
    "иксель эс": "xlsx",
    "икс эс": "xlsx",
    "иксэльэс": "xlsx",
}

_EXTENSION_RE = re.compile(
    r"(?P<dot>\.)(?P<extension>[a-zа-яё]+(?:\s+[a-zа-яё]+)?)\b",
    flags=re.IGNORECASE,
)


def _replace_spoken_punctuation(text: str) -> str:
    for pattern, replacement in _SPOKEN_PUNCTUATION:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _replace_extension(match: re.Match[str]) -> str:
    extension = " ".join(match.group("extension").casefold().split())
    normalized = _EXTENSION_ALIASES.get(extension)
    if normalized is None:
        return match.group(0)
    return "." + normalized


def normalize_voice_command(text: str) -> str:
    """Normalize safe, speech-specific punctuation and file extensions.

    The function deliberately does not perform broad fuzzy correction of words.
    It only fixes forms that are unambiguous in a voice command, leaving the
    existing router, alias resolver and file resolver responsible for matching
    actual objects.
    """
    text = unicodedata.normalize("NFKC", str(text)).strip()
    if not text:
        return ""

    text = " ".join(text.split())
    text = _replace_spoken_punctuation(text)
    text = _EXTENSION_RE.sub(_replace_extension, text)

    # Whisper may leave spaces around punctuation after the spoken replacement.
    text = re.sub(r"\s*([._/-])\s*", r"\1", text)
    text = re.sub(r"\s+([,;:!?])", r"\1", text)
    text = re.sub(r"([,;:!?])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text
