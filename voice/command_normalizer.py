from __future__ import annotations

import re
import unicodedata


_SPOKEN_PUNCTUATION = (
    (r"\bнижн(?:ее|яя)\s+подч[её]ркивание\b", "_"),
    (r"\bнижн(?:ее|яя)\s+подчеркивание\b", "_"),
    (r"\bнижн(?:яя|ее)\s+черта\b", "_"),
    (r"\bнижн(?:яя|ее)\s+прочерк\b", "_"),
    (r"\bнижн(?:яя|ее)\s+почерк\b", "_"),
    (r"\bподч[её]ркивание\b", "_"),
    (r"\bподчеркивание\b", "_"),
    (r"\bточк(?:а|у|ой)\b", "."),
    (r"\bобратн(?:ый|ая)\s+слэш\b", lambda _: "\\"),
    (r"\bсл[её]ш\b", "/"),
    (r"\bслэш\b", "/"),
    (r"\bдефис\b", "-"),
    (r"\bтире\b", "-"),
    (r"\bвопросительн(?:ый|ая)\s+знак\b", "?"),
    (r"\bзнак\s+вопроса\b", "?"),
    (r"\bвосклицательн(?:ый|ая)\s+знак\b", "!"),
    (r"\bзнак\s+восклицания\b", "!"),
    (r"\bдвоеточие\b", ":"),
    (r"\bточка\s+с\s+запятой\b", ";"),
    (r"\bзапятая\b", ","),
)

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
    "док": "doc",
    "документ": "doc",
    "докэкс": "docx",
    "ворд": "docx",
    "пдф": "pdf",
    "пэ дэ эф": "pdf",
    "пнг": "png",
    "джипег": "jpg",
    "джейпег": "jpg",
    "жпег": "jpg",
    "экзэ": "exe",
    "экзе": "exe",
    "бат": "bat",
    "бэт": "bat",
    "би эй ти": "bat",
    "би-эй-ти": "bat",
}

_EXTENSION_NAMES = sorted(_EXTENSION_ALIASES, key=len, reverse=True)
_SPOKEN_EXTENSION_RE = re.compile(
    r"(?P<separator>\s*)\bточк(?:а|у|ой)\s+(?P<extension>"
    + "|".join(re.escape(name) for name in _EXTENSION_NAMES)
    + r")\b",
    flags=re.IGNORECASE,
)

_EXTENSION_RE = re.compile(
    r"(?P<dot>\.)(?:\s*)(?P<extension>[a-zа-яё]+(?:\s+[a-zа-яё]+)?)\b",
    flags=re.IGNORECASE,
)


def _replace_spoken_extension(match: re.Match[str]) -> str:
    extension = " ".join(match.group("extension").casefold().split())
    return "." + _EXTENSION_ALIASES[extension]


def _replace_spoken_punctuation(text: str) -> str:
    text = _SPOKEN_EXTENSION_RE.sub(_replace_spoken_extension, text)
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
    """Normalize safe, speech-specific punctuation and file extensions."""
    text = unicodedata.normalize("NFKC", str(text)).strip()
    if not text:
        return ""

    text = " ".join(text.split())
    text = _replace_spoken_punctuation(text)
    text = _EXTENSION_RE.sub(_replace_extension, text)

    text = re.sub(r"\s+\.", ".", text)
    text = re.sub(r"\s*([_\\/-])\s*", r"\1", text)
    text = re.sub(r"\s+([,;:!?])", r"\1", text)
    # Do not insert a space after a colon: colons are part of common URLs
    # such as https://example.com and localhost:11434.
    text = re.sub(r"([,;!?])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text
