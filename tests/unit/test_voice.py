from __future__ import annotations

import pytest

from voice.command_normalizer import normalize_voice_command


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("создай файл test точка txt", "создай файл test.txt"),
        ("открой https://example.com", "открой https://example.com"),
        ("test подчеркивание file точка py", "test_file.py"),
        ("путь слэш папка слэш файл", "путь/папка/файл"),
        ("test дефис file", "test-file"),
    ],
)
def test_voice_command_normalization(source, expected):
    assert normalize_voice_command(source) == expected


def test_voice_normalizer_is_idempotent_for_normalized_text():
    value = "создай файл test_file.py"
    assert normalize_voice_command(value) == value


def test_voice_normalizer_handles_empty_input():
    assert normalize_voice_command("") == ""
    assert normalize_voice_command("   ") == ""
