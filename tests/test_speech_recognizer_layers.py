from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from voice.speech_recognizer import SpeechRecognizer


class FakeWhisperModel:
    def __init__(self, source, *, device, compute_type, cpu_threads):
        self.source = source
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = cpu_threads
        self.transcribe_calls = []

    def transcribe(self, audio, **kwargs):
        self.transcribe_calls.append((audio, kwargs))
        return [SimpleNamespace(text=" hello "), SimpleNamespace(text="world")], SimpleNamespace()


def test_resample_changes_length_and_returns_float32():
    audio = np.linspace(-1, 1, 160, dtype=np.float32)

    result = SpeechRecognizer._resample(audio, 8000, 16000)

    assert len(result) == 320
    assert result.dtype == np.float32


def test_resample_returns_original_for_same_or_invalid_rate():
    audio = np.asarray([1.0, 2.0], dtype=np.float32)

    assert SpeechRecognizer._resample(audio, 16000, 16000) is audio
    assert SpeechRecognizer._resample(audio, 0, 16000) is audio


def test_update_settings_clamps_and_updates_values():
    recognizer = SpeechRecognizer()
    recognizer.update_settings(
        beam_size=0,
        vad_filter=False,
        without_timestamps=False,
        condition_on_previous_text=True,
    )

    assert recognizer.beam_size == 1
    assert recognizer.vad_filter is False
    assert recognizer.without_timestamps is False
    assert recognizer.condition_on_previous_text is True


def test_empty_audio_returns_empty_without_model_download():
    recognizer = SpeechRecognizer()
    dependency = Mock()

    with patch("voice.speech_recognizer.get_dependency_manager", return_value=dependency),          patch("voice.speech_recognizer.WhisperModel") as whisper:
        result = recognizer.transcribe(np.empty(0, dtype=np.float32))

    assert result == ""
    dependency.ensure_whisper_model.assert_not_called()
    whisper.assert_not_called()


def test_transcribe_uses_dependency_manager_only_for_non_local_model():
    recognizer = SpeechRecognizer(
        model_name="small",
        device="cpu",
        compute_type="int8",
        language="ru",
        cpu_threads=4,
        beam_size=2,
    )
    dependency = Mock()
    dependency.ensure_whisper_model.return_value = "small"

    fake_model = FakeWhisperModel(
        "small", device="cpu", compute_type="int8", cpu_threads=4
    )

    with patch("voice.speech_recognizer.get_dependency_manager", return_value=dependency),          patch("voice.speech_recognizer.WhisperModel", return_value=fake_model):
        result = recognizer.transcribe(
            np.ones(16000, dtype=np.float32),
            sample_rate=16000,
        )

    assert result == "hello world"
    dependency.ensure_whisper_model.assert_called_once_with("small")
    assert len(fake_model.transcribe_calls) == 1
    _, kwargs = fake_model.transcribe_calls[0]
    assert kwargs["language"] == "ru"
    assert kwargs["beam_size"] == 2
    assert recognizer.last_stats is not None
    assert recognizer.last_stats.audio_duration_s == 1.0
    assert recognizer.last_stats.model_loaded_this_request is True


def test_local_model_path_skips_dependency_manager(tmp_path):
    model_dir = tmp_path / "whisper"
    model_dir.mkdir()
    recognizer = SpeechRecognizer(model_name=str(model_dir))

    dependency = Mock()
    fake_model = FakeWhisperModel(
        str(model_dir), device="cpu", compute_type="int8", cpu_threads=4
    )

    with patch("voice.speech_recognizer.get_dependency_manager", return_value=dependency),          patch("voice.speech_recognizer.WhisperModel", return_value=fake_model):
        result = recognizer.transcribe(
            np.ones(8000, dtype=np.float32),
            sample_rate=8000,
        )

    assert result == "hello world"
    dependency.ensure_whisper_model.assert_not_called()
    assert fake_model.transcribe_calls[0][0].dtype == np.float32
    assert len(fake_model.transcribe_calls[0][0]) == 16000
    assert recognizer.last_stats.real_time_factor >= 0


def test_close_releases_model_and_marks_unload_time():
    recognizer = SpeechRecognizer()
    fake_model = FakeWhisperModel(
        "small", device="cpu", compute_type="int8", cpu_threads=4
    )
    recognizer._model = fake_model

    result = recognizer.close()

    assert result is recognizer.last_stats
    assert result is None or result.unload_time_s is None or result.unload_time_s >= 0
    assert recognizer._model is None
