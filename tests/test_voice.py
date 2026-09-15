import numpy as np

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
    assert created[0][0] == ("base",)
    assert created[0][1]["device"] == "cpu"
    assert created[0][1]["compute_type"] == "int8"


def test_speech_recognizer_ignores_empty_audio(monkeypatch):
    def fail_if_created(*args, **kwargs):
        raise AssertionError("Whisper model should not load for empty audio")

    monkeypatch.setattr("voice.speech_recognizer.WhisperModel", fail_if_created)
    recognizer = SpeechRecognizer()

    assert recognizer.transcribe(np.empty(0, dtype=np.float32)) == ""
