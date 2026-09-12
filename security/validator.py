from __future__ import annotations

from urllib.parse import urlparse


def validate_non_empty(value: str, field_name: str = "значение") -> str:
    value = str(value or "").strip()
    if not value:
        raise ValueError(f"Не указано {field_name}.")
    return value


def validate_url(value: str) -> str:
    value = validate_non_empty(value, "URL")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Разрешены только корректные HTTP/HTTPS URL.")
    return value


def validate_tool_name(value: str) -> str:
    value = validate_non_empty(value, "имя инструмента")
    if any(char in value for char in "\\/\r\n"):
        raise ValueError("Недопустимое имя инструмента.")
    return value
