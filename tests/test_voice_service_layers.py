from __future__ import annotations

from concurrent.futures import Future

from unittest.mock import Mock, patch
import numpy as np
import pytest

from core.events import EventBus
from voice.controller import VoiceService


class ManualRunner:
    def __init__(self):
        self.submitted = []

    def submit(self, function, *args, **kwargs):
        future = Future()
        self.submitted.append((future, function, args, kwargs))
        return future

    def shutdown(self, *args, **kwargs):
        pass


@pytest.fixture
def voice_service():
    runner = ManualRunner()
    recorder = Mock()
    recorder.is_recording = False
    recognizer = Mock()
    recognizer.model_name = "small"
    recognizer.device = "cpu"
    recognizer.compute_type = "int8"
    recognizer.language = "ru"
    recognizer.cpu_threads = 4
    recognizer.vad_filter = True
    recognizer.without_timestamps = True
    recognizer.condition_on_previous_text = False
    recognizer.last_stats = None

    config = {
        "voice": {
            "sample_rate": 16000,
            "channels": 1,
            "silence_duration": 2.0,
            "input_device": None,
            "model": "small",
            "device": "cpu",
            "compute_type": "int8",
            "cpu_threads": 4,
            "beam_size": 1,
            "vad_filter": True,
            "without_timestamps": True,
            "condition_on_previous_text": False,
            "language": "ru",
            "min_duration": 0.25,
        }
    }

    with patch("voice.controller.find_supported_sample_rate", return_value=16000),          patch("voice.controller.MicrophoneRecorder", return_value=recorder),          patch("voice.controller.SpeechRecognizer", return_value=recognizer):
        service = VoiceService(config, EventBus(), runner)

    service.recorder = recorder
    service.recognizer = recognizer
    service.tasks = runner
    return service, recorder, recognizer, runner


def test_start_emits_listening_and_starts_recorder(voice_service):
    service, recorder, _, _ = voice_service
    service._start_silence_monitor = Mock()

    seen = []
    service.events.subscribe("voice.listening_changed", lambda value: seen.append(value))

    service.start()

    recorder.start.assert_called_once()
    service._start_silence_monitor.assert_called_once()
    assert seen == [True]


def test_start_does_not_duplicate_recording(voice_service):
    service, recorder, _, _ = voice_service
    recorder.is_recording = True
    service._start_silence_monitor = Mock()

    service.start()

    recorder.start.assert_not_called()


def test_stop_skips_transcription_for_too_short_audio(voice_service):
    service, recorder, _, runner = voice_service
    recorder.is_recording = True
    recorder.stop.return_value = np.zeros((10, 1), dtype=np.float32)

    service.stop()

    assert not runner.submitted
    assert service.transcribing() is False


def test_transcribe_normalizes_text_and_emits_stats_and_transcript(voice_service):
    service, _, recognizer, runner = voice_service
    recognizer.transcribe.return_value = "найди файл report точка txt"
    recognizer.last_stats = {"model": "small"}

    transcripts = []
    stats = []
    service.events.subscribe("voice.transcript_ready", transcripts.append)
    service.events.subscribe("voice.whisper_stats", stats.append)

    audio = np.zeros((5000, 1), dtype=np.float32)
    service._transcribe(audio)

    future, function, args, _ = runner.submitted[0]
    assert function == recognizer.transcribe
    assert args[1] == 16000

    future.set_result(function(*args))
    service._transcription_done(future)

    assert transcripts == ["найди файл report.txt"]
    assert stats == [{"model": "small"}]
    assert service.transcribing() is False


def test_transcription_failure_emits_error(voice_service):
    service, _, recognizer, runner = voice_service
    recognizer.transcribe.side_effect = RuntimeError("broken")

    errors = []
    service.events.subscribe("voice.error", errors.append)

    service._transcribe(np.zeros((5000, 1), dtype=np.float32))
    future, function, args, _ = runner.submitted[0]
    try:
        function(*args)
    except RuntimeError:
        pass
    future.set_exception(RuntimeError("broken"))
    service._transcription_done(future)

    assert any("Не удалось распознать речь" in item for item in errors)


def test_test_microphone_returns_peak_and_rms(voice_service):
    service, _, _, _ = voice_service
    audio = np.asarray([[0.0], [0.5], [-0.5], [1.0]], dtype=np.float32)

    with patch("voice.controller.find_supported_sample_rate", return_value=48000),          patch("voice.controller.sd.rec", return_value=audio):
        result = service.test_microphone(7)

    assert result["success"] is True
    assert result["rate"] == 48000
    assert result["peak"] == pytest.approx(1.0)
    assert result["rms"] == pytest.approx(np.sqrt((0.0 + 0.25 + 0.25 + 1.0) / 4))


def test_list_microphones_returns_default_and_selects_named_device(voice_service):
    service, _, _, _ = voice_service
    service._configured_device_name = "USB Mic"
    service._configured_device = None

    devices = [
        {"name": "USB Mic", "max_input_channels": 1, "hostapi": 0},
        {"name": "Speakers", "max_input_channels": 0, "hostapi": 0},
    ]
    hostapis = [{"name": "Windows WASAPI"}]

    with patch("voice.controller.sd.query_devices", return_value=devices),          patch("voice.controller.sd.query_hostapis", return_value=hostapis):
        result = service.list_microphones()

    assert result["success"] is True
    assert any(item["name"] == "USB Mic" and item["selected"] for item in result["devices"])


def test_apply_config_reuses_compatible_recognizer_and_updates_settings(voice_service):
    service, _, recognizer, _ = voice_service
    service.recognizer = recognizer

    with patch("voice.controller.find_supported_sample_rate", return_value=16000),          patch("voice.controller.MicrophoneRecorder", return_value=service.recorder):
        service.apply_config({
            "voice": {
                "sample_rate": 16000,
                "channels": 1,
                "model": "small",
                "device": "cpu",
                "compute_type": "int8",
                "cpu_threads": 4,
                "beam_size": 3,
                "vad_filter": True,
                "without_timestamps": True,
                "condition_on_previous_text": False,
                "language": "ru",
            }
        })

    recognizer.update_settings.assert_called_once()
    recognizer.close.assert_not_called()


def test_friendly_microphone_error_contains_original_error():
    error = VoiceService._friendly_microphone_error(RuntimeError("no device"))
    assert "no device" in error
    assert "микрофону" in error


def test_close_closes_recognizer_and_recorder(voice_service):
    service, recorder, recognizer, _ = voice_service
    recorder.is_recording = True
    recorder.stop.return_value = []
    recognizer.close.return_value = {"model": "small"}

    service.close()

    recorder.stop.assert_called_once()
    recognizer.close.assert_called_once()
    assert service.recognizer is None
