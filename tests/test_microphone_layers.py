from __future__ import annotations

from unittest.mock import Mock, patch

import numpy as np

from voice.microphone import MicrophoneRecorder


def test_microphone_recorder_initial_state():
    recorder = MicrophoneRecorder(sample_rate=16000, channels=1)
    assert recorder.is_recording is False
    assert recorder.has_voice is False
    assert recorder.silence_duration == 0.0


def test_microphone_recorder_start_creates_and_starts_stream():
    stream = Mock()

    with patch("voice.microphone.sd.InputStream", return_value=stream) as factory:
        recorder = MicrophoneRecorder(sample_rate=16000, channels=1, device=3)
        recorder.start()

    assert recorder.is_recording is True
    factory.assert_called_once()
    stream.start.assert_called_once()


def test_microphone_recorder_callback_tracks_voice_and_silence(monkeypatch):
    recorder = MicrophoneRecorder()
    now = iter([10.0, 12.0])
    monkeypatch.setattr("voice.microphone.time.monotonic", lambda: next(now))

    voice_chunk = np.asarray([[0.5], [-0.5]], dtype=np.float32)
    silent_chunk = np.zeros((2, 1), dtype=np.float32)

    recorder._callback(voice_chunk, 2, None, None)
    assert recorder.has_voice is True
    assert recorder.silence_duration == 2.0

    recorder._callback(silent_chunk, 2, None, None)


def test_microphone_recorder_stop_returns_mono_audio_and_resets_state():
    stream = Mock()
    recorder = MicrophoneRecorder(sample_rate=16000, channels=2)
    recorder._stream = stream
    recorder._chunks = [
        np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        np.asarray([[0.5, 0.5]], dtype=np.float32),
    ]
    recorder._has_voice = True
    recorder._last_voice_at = 1.0

    audio = recorder.stop()

    assert audio.dtype == np.float32
    assert np.allclose(audio, [0.5, 0.5, 0.5])
    assert recorder.is_recording is False
    assert recorder.has_voice is False


def test_microphone_recorder_stop_without_stream_returns_empty():
    recorder = MicrophoneRecorder()
    result = recorder.stop()
    assert result.size == 0


def test_microphone_recorder_start_failure_resets_stream():
    with patch("voice.microphone.sd.InputStream", side_effect=OSError("no mic")):
        recorder = MicrophoneRecorder()
        try:
            recorder.start()
        except OSError:
            pass

    assert recorder.is_recording is False
