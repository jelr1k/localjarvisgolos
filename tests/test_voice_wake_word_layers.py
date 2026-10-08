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


def test_detector_config_keeps_original_device_when_shared_resolution_fails():
    config = {
        "voice": {
            "wake_word_enabled": True,
            "wake_word": "Jarvis",
            "input_device": 4,
            "sample_rate": 16000,
        }
    }

    with patch("voice.wake_word.resolve_shared_input_device", side_effect=RuntimeError("audio unavailable")):
        detector = wake_word.WakeWordDetector(config)

    assert detector.device == 4
    assert detector.sample_rate == 16000
    detector.close()


def test_word_in_vocabulary_returns_false_when_model_vocabulary_is_missing(tmp_path):
    assert wake_word._word_in_vocabulary(tmp_path, "Jarvis") is False


def test_download_model_skips_network_when_model_is_already_present(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "am").mkdir()

    with patch("voice.wake_word.urllib.request.build_opener") as build_opener:
        assert wake_word._download_model(model_dir) == model_dir

    build_opener.assert_not_called()


def test_download_model_rejects_invalid_extraction(tmp_path):
    model_dir = tmp_path / "model"
    archive = model_dir.parent / f"{model_dir.name}.zip"
    archive.write_bytes(b"not-a-real-zip")

    with patch("voice.wake_word.urllib.request.build_opener") as build_opener:
        opener = Mock()
        build_opener.return_value = opener
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.side_effect = [b"broken", b""]
        opener.open.return_value = response

        with pytest.raises((RuntimeError, Exception)):
            wake_word._download_model(model_dir)


def test_detector_run_publishes_error_and_stops_cleanly():
    config = {"voice": {"wake_word_enabled": True}}
    events = Mock()
    detector = wake_word.WakeWordDetector(
        config,
        event_bus=events,
    )

    with patch("voice.wake_word._download_model", side_effect=RuntimeError("model unavailable")):
        detector._run()

    emitted = [call.args for call in events.emit.call_args_list]
    assert any(item[0] == "wake_word.error" and "model unavailable" in item[1] for item in emitted)
    assert any(item[0] == "wake_word.listening_changed" and item[1] is False for item in emitted)
