from voice.command_normalizer import normalize_voice_command


def test_normalize_spoken_txt_extension():
    assert normalize_voice_command("Где находится файл tool_test точка текстей?") == "Где находится файл tool_test.txt?"


def test_normalize_spoken_punctuation_and_extension():
    assert normalize_voice_command("найди файл report нижнее подчеркивание точка джейсон") == "найди файл report.json"


def test_normalize_common_code_extensions():
    assert normalize_voice_command("прочитай main точка пайтон") == "прочитай main.py"
    assert normalize_voice_command("прочитай README точка эмдэ") == "прочитай README.md"


def test_normalize_spoken_backslash():
    assert normalize_voice_command("путь обратный слэш папка") == "путь\\папка"


def test_normalize_does_not_change_ordinary_text():
    text = "Найди текстовый файл с описанием проекта"
    assert normalize_voice_command(text) == text


def test_normalize_is_idempotent_for_normal_text():
    text = "Где находится файл tool_test.txt?"
    normalized = normalize_voice_command(text)
    assert normalized == text
    assert normalize_voice_command(normalized) == normalized
