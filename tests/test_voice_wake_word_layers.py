from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from voice import wake_word


@pytest.mark.parametrize(
    ("text", "expected"),
    [("  ДЖАРВИС  ", "джарвис"), ("ёЁ", "ее"), ("a   b", "a b")],
)
def test_wake_word_normalization(text, expected):
    assert wake_word._normalize(text) == expected
    assert wake_word._compact(text) == expected.replace(" ", "")


def test_jarvis_variants_and_candidates_include_russian_and_latin():
    variants = wake_word._wake_word_variants("Jarvis")
    candidates = wake_word._wake_word_candidates("Jarvis")

    assert variants == ("джарвис", "джервис", "jarvis")
    assert "джарвис" in candidates
    assert "jarvis" in candidates


def test_transliteration_and_similarity():
    assert wake_word._transliterate_to_russian("zhervis") == "жервис"
    assert wake_word._similarity("джарвис", "джарвис") == 1.0


@pytest.mark.parametrize(
    "text",
    ["джарвис", "ДЖАРВИС", "скажи джарвис", "джервис", "jarvis"],
)
def test_contains_wake_word_accepts_common_forms(text):
    assert wake_word._contains_wake_word(text, "Jarvis") is True


@pytest.mark.parametrize("text", ["привет", "марвис", "", "обычный текст"])
def test_contains_wake_word_rejects_unrelated_text(text):
    assert wake_word._contains_wake_word(text, "Jarvis") is False


def test_word_in_vocabulary(tmp_path):
    graph = tmp_path / "graph"
    graph.mkdir()
    (graph / "words.txt").write_text("джарвис 10\nhello 20\n", encoding="utf-8")

    assert wake_word._word_in_vocabulary(tmp_path, "Jarvis") is True
    assert wake_word._word_in_vocabulary(tmp_path, "Other") is False


def test_detector_config_resolves_named_device_and_sample_rate():
    config = {
        "voice": {
            "wake_word_enabled": True,
            "wake_word": "Jarvis",
            "input_device_name": "USB Mic",
            "input_device": 1,
            "sample_rate": 16000,
        }
    }

    with patch("voice.wake_word.find_input_device_by_name", return_value={"index": 7}),          patch("voice.wake_word.resolve_shared_input_device", side_effect=lambda value: value),          patch("voice.wake_word.find_supported_sample_rate", return_value=48000):
        detector = wake_word.WakeWordDetector(config)

    assert detector.enabled is True
    assert detector.device == 7
    assert detector.sample_rate == 48000
    detector.close()


def test_detector_disabled_does_not_start_thread():
    config = {"voice": {"wake_word_enabled": False}}

    with patch("voice.wake_word.resolve_shared_input_device", side_effect=lambda value: value),          patch("voice.wake_word.find_supported_sample_rate", return_value=16000),          patch("voice.wake_word.threading.Thread") as thread:
        detector = wake_word.WakeWordDetector(config)
        detector.start()

    thread.assert_not_called()
    detector.close()
