from __future__ import annotations

import json
import sys
import time
from types import ModuleType
from pathlib import Path
from threading import Event

import numpy as np
import pytest

from core.events import EventBus
from voice.tts import (
    PiperTTSBackend,
    SUPPORTED_TTS_VOICES,
    AudioAssetManager,
    TTSConfigurationError,
    TTSError,
    TTSService,
    TTSVoiceNotInstalledError,
    prepare_speech_text,
    split_speech_text,
)


class FakeBackend:
    def __init__(self):
        self.voice_name = "ru_RU-dmitri-medium"
        self.speed = 1.0
        self.volume = 0.85
        self.synthesized_settings = []

    def configure(self, voice_name, speed=1.0, volume=0.85):
        if voice_name not in SUPPORTED_TTS_VOICES:
            raise TTSConfigurationError("unknown voice")
        self.voice_name = voice_name
        self.speed = float(speed)
        self.volume = float(volume)

    def voice_status(self, voice_name=None):
        return "installed"

    def ensure_voice(self, voice_name=None):
        return Path("fake-voice.onnx")

    def synthesize(self, text):
        assert text.strip()
        self.synthesized_settings.append((self.voice_name, self.speed, self.volume))
        return np.full(2205, 0.05, dtype=np.float32), 22050


class FakePlayer:
    def __init__(self):
        self.played = []
        self.finished = Event()

    def play(self, audio, sample_rate):
        self.played.append((audio, sample_rate))
        self.finished.set()

    def stop(self):
        self.finished.set()


def test_prepare_speech_text_removes_markdown_and_links():
    result = prepare_speech_text(
        "# Заголовок\nВот **важно**, [ссылка](https://example.com) и `код`. "
        "```python\nprint('secret')\n```"
    )

    assert "Заголовок" in result
    assert "важно" in result
    assert "ссылка" in result
    assert "example.com" not in result
    assert "print" not in result
    assert "код" not in result


def test_prepare_speech_text_limits_extremely_long_input():
    result = prepare_speech_text("слово " * 5000)

    assert len(result) <= 16050
    assert result.endswith("Остальная часть ответа не озвучена.")


def test_split_speech_text_chunks_long_responses():
    text = "Это тестовое предложение для проверки границ фрагментов. " * 12

    chunks = split_speech_text(text, max_chars=100)

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert "тестовое предложение" in " ".join(chunks)


def test_piper_backend_only_accepts_explicitly_supported_voices(tmp_path):
    backend = PiperTTSBackend(model_dir=tmp_path)

    assert set(SUPPORTED_TTS_VOICES) == {
        "ru_RU-dmitri-medium",
        "ru_RU-irina-medium",
        "ru_RU-ruslan-medium",
    }
    model_path, config_path = backend.paths_for()

    assert model_path.name == "ru_RU-dmitri-medium.onnx"
    assert config_path.name == "ru_RU-dmitri-medium.onnx.json"
    assert backend.voice_status() == "missing"

    with pytest.raises(TTSConfigurationError, match="Неподдерживаемый голос"):
        backend.configure("untrusted-voice", speed=1.0, volume=0.85)


def test_piper_backend_status_checks_model_and_config(tmp_path):
    backend = PiperTTSBackend(model_dir=tmp_path)
    model_path, config_path = backend.paths_for()
    model_path.write_bytes(b"x" * 2048)
    config_path.write_text(
        json.dumps({"audio": {"sample_rate": 22050}, "test_padding": "x" * 100}),
        encoding="utf-8",
    )

    assert backend.voice_status() == "installed"

    config_path.write_text("{broken json", encoding="utf-8")
    assert backend.voice_status() == "missing"


def test_piper_backend_requires_downloaded_model_before_synthesis(tmp_path):
    backend = PiperTTSBackend(model_dir=tmp_path)

    with pytest.raises(TTSVoiceNotInstalledError, match="Голос TTS не установлен"):
        backend.synthesize("Привет")


def test_piper_load_error_explains_recovery_and_preserves_cause(tmp_path, monkeypatch):
    backend = PiperTTSBackend(model_dir=tmp_path)
    monkeypatch.setattr(backend, "voice_status", lambda voice_name=None: "installed")

    class BrokenPiperVoice:
        @staticmethod
        def load(_model_path):
            raise RuntimeError("test ONNX runtime failure")

    piper_module = ModuleType("piper")
    piper_module.PiperVoice = BrokenPiperVoice
    monkeypatch.setitem(sys.modules, "piper", piper_module)

    with pytest.raises(TTSError, match="test ONNX runtime failure") as error:
        backend.synthesize("Проверочная фраза")

    message = str(error.value)
    assert "повторно" in message
    assert "%APPDATA%\\Jarvis\\tts\\voices" in message
    assert "logs\\tts.log" in message


def test_tts_service_does_not_speak_automatically_when_disabled(tmp_path):
    events = EventBus()
    player = FakePlayer()
    service = TTSService(
        events,
        {"tts": {"enabled": False}},
        backend=FakeBackend(),
        player=player,
        asset_manager=AudioAssetManager(tmp_path / "assets"),
    )

    try:
        assert service.speak("Это не должно прозвучать.") is False
        assert player.played == []
    finally:
        service.close()


def test_tts_service_queues_and_plays_when_enabled(tmp_path):
    events = EventBus()
    player = FakePlayer()
    service = TTSService(
        events,
        {"tts": {"enabled": True, "voice": "ru_RU-dmitri-medium", "speed": 1.0, "volume": 0.85}},
        backend=FakeBackend(),
        player=player,
        asset_manager=AudioAssetManager(tmp_path / "assets"),
    )

    try:
        assert service.speak("Проверка работы синтеза.", source="unit-test") is True
        assert player.finished.wait(timeout=2.0)
        assert len(player.played) == 1
        assert player.played[0][1] == 22050
    finally:
        service.close()


def test_tts_manual_test_works_even_when_auto_speech_is_disabled(tmp_path):
    player = FakePlayer()
    backend = FakeBackend()
    service = TTSService(
        EventBus(),
        {"tts": {"enabled": False}},
        backend=backend,
        player=player,
        asset_manager=AudioAssetManager(tmp_path / "assets"),
    )

    try:
        assert service.test("ru_RU-irina-medium", 1.1, 0.5) is True
        assert player.finished.wait(timeout=2.0)
        assert len(player.played) == 1
        assert backend.synthesized_settings == [("ru_RU-irina-medium", 1.1, 0.5)]
        # Preview settings are temporary; only Save should update the active voice.
        assert (backend.voice_name, backend.speed, backend.volume) == ("ru_RU-dmitri-medium", 1.0, 0.85)
    finally:
        service.close()


def test_tts_service_receives_shared_speech_requests_from_event_bus(tmp_path):
    events = EventBus()
    player = FakePlayer()
    service = TTSService(
        events,
        {"tts": {"enabled": True}},
        backend=FakeBackend(),
        player=player,
        asset_manager=AudioAssetManager(tmp_path / "assets"),
    )

    try:
        events.emit("speech.requested", "Общий запрос озвучивания.", "assistant")
        assert player.finished.wait(timeout=2.0)
        assert len(player.played) == 1
    finally:
        service.close()


def test_tts_service_plays_prepared_recording_for_matching_text(tmp_path):
    events = EventBus()
    backend = FakeBackend()
    player = FakePlayer()
    assets = AudioAssetManager(tmp_path / "assets")
    source = assets.save_cached_audio("a" * 64, np.full(2205, 0.2, dtype=np.float32), 22050)
    assets.register_prepared_file(
        "ru_RU-dmitri-medium", "greeting.hello", source,
        text="Привет! Я Джарвис."
    )
    service = TTSService(
        events,
        {"tts": {"enabled": True, "voice": "ru_RU-dmitri-medium", "speed": 1.0, "volume": 0.85}},
        backend=backend,
        player=player,
        asset_manager=assets,
    )
    try:
        assert service.speak("Привет!   Я Джарвис.", source="unit-test") is True
        assert player.finished.wait(timeout=2.0)
        assert len(player.played) == 1
        assert backend.synthesized_settings == []
        assert service.metrics.snapshot().prepared_audio_hits == 1
    finally:
        service.close()
