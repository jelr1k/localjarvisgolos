import numpy as np

from core.config_manager import DEFAULTS
from voice.devices import find_supported_sample_rate
from voice.microphone import MicrophoneRecorder
from voice.speech_recognizer import SpeechRecognizer


def test_microphone_stop_without_recording_returns_empty_audio():
    recorder = MicrophoneRecorder()
    audio = recorder.stop()
    assert isinstance(audio, np.ndarray)
    assert audio.size == 0


def test_speech_recognizer_loads_model_lazily(monkeypatch):
    created = []

    class FakeModel:
        def __init__(self, *args, **kwargs):
            created.append((args, kwargs))

        def transcribe(self, audio, **kwargs):
            class Segment:
                text = " Привет, Джарвис! "

            return [Segment()], object()

    monkeypatch.setattr("voice.speech_recognizer.WhisperModel", FakeModel)
    recognizer = SpeechRecognizer()

    assert created == []
    text = recognizer.transcribe(np.ones(1600, dtype=np.float32))

    assert text == "Привет, Джарвис!"
    assert len(created) == 1
    assert created[0][0] == ("small",)
    assert created[0][1]["device"] == "cpu"
    assert created[0][1]["compute_type"] == "int8"


def test_speech_recognizer_uses_existing_local_model_path(monkeypatch, tmp_path):
    created = []

    class FakeModel:
        def __init__(self, *args, **kwargs):
            created.append((args, kwargs))

        def transcribe(self, audio, **kwargs):
            class Segment:
                text = " локальная модель "

            return [Segment()], object()

    monkeypatch.setattr("voice.speech_recognizer.WhisperModel", FakeModel)
    model_dir = tmp_path / "faster-whisper-large-v3"
    model_dir.mkdir()

    recognizer = SpeechRecognizer(model_name=str(model_dir))
    assert recognizer.transcribe(np.ones(1600, dtype=np.float32)) == "локальная модель"
    assert created[0][0] == (str(model_dir.resolve()),)


def test_speech_recognizer_ignores_empty_audio(monkeypatch):
    def fail_if_created(*args, **kwargs):
        raise AssertionError("Whisper model should not load for empty audio")

    monkeypatch.setattr("voice.speech_recognizer.WhisperModel", fail_if_created)
    recognizer = SpeechRecognizer()

    assert recognizer.transcribe(np.empty(0, dtype=np.float32)) == ""


def test_default_voice_configuration_is_complete():
    assert DEFAULTS["voice"]["sample_rate"] == 16000
    assert DEFAULTS["voice"]["channels"] == 1
    assert DEFAULTS["voice"]["input_device"] is None
    assert DEFAULTS["voice"]["model"] == "small"


def test_find_supported_sample_rate_prefers_requested_rate(monkeypatch):
    calls = []

    def check_input_settings(**kwargs):
        calls.append(kwargs["samplerate"])
        if kwargs["samplerate"] != 16000:
            raise ValueError("unsupported")

    monkeypatch.setattr("voice.devices.sd.check_input_settings", check_input_settings)

    assert find_supported_sample_rate(device=3, channels=1, preferred=16000) == 16000
    assert calls == [16000]


def test_find_supported_sample_rate_falls_back(monkeypatch):
    calls = []

    def check_input_settings(**kwargs):
        calls.append(kwargs["samplerate"])
        if kwargs["samplerate"] != 48000:
            raise ValueError("unsupported")

    monkeypatch.setattr("voice.devices.sd.check_input_settings", check_input_settings)

    assert find_supported_sample_rate(device=3, channels=1, preferred=16000) == 48000
    assert calls == [16000, 48000]


def test_speech_recognizer_resamples_to_whisper_rate(monkeypatch):
    captured = []

    class FakeModel:
        def transcribe(self, audio, **kwargs):
            captured.append(audio)

            class Segment:
                text = " тест "

            return [Segment()], object()

    monkeypatch.setattr("voice.speech_recognizer.WhisperModel", lambda *args, **kwargs: FakeModel())
    recognizer = SpeechRecognizer()

    source = np.linspace(-1, 1, 48000, dtype=np.float32)
    assert recognizer.transcribe(source, sample_rate=48000) == "тест"
    assert len(captured) == 1
    assert len(captured[0]) == 16000
