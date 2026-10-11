from __future__ import annotations

import numpy as np
import pytest

from voice.tts import AudioAssetManager, SpeechRequest, TTSMetrics, VoiceManager, VoiceProfile


def _profile(voice_id: str = "ru_RU-dmitri-medium", *, kind: str = "builtin", speed: float = 1.0) -> VoiceProfile:
    return VoiceProfile(voice_id, voice_id, "piper", voice_id, kind=kind, settings={"speed": speed, "volume": 0.85})


def test_voice_manager_persists_custom_profiles_and_active_voice(tmp_path):
    path = tmp_path / "voice_profiles.json"
    built_in = _profile()
    custom = VoiceProfile("custom-kirill", "Custom voice", "future-engine", "reference-profile", kind="custom",
                          reference_audio="C:/Users/example/AppData/Jarvis/tts/references/sample.wav", reference_text="Проверочная фраза.")
    manager = VoiceManager(path, builtin_profiles=[built_in])
    manager.add_voice(custom)
    manager.set_active_voice(custom.voice_id)

    restored = VoiceManager(path, builtin_profiles=[built_in])
    assert restored.active_voice_id == custom.voice_id
    assert restored.get_voice(custom.voice_id).reference_text == "Проверочная фраза."
    assert {voice.voice_id for voice in restored.list_voices()} == {built_in.voice_id, custom.voice_id}
    with pytest.raises(ValueError, match="Built-in"):
        restored.remove_voice(built_in.voice_id)


def test_voice_profile_rejects_path_like_ids():
    with pytest.raises(ValueError, match="voice_id"):
        VoiceProfile("..\\evil", "Bad", "piper", "model")


def test_cache_key_includes_text_voice_engine_model_and_settings():
    text = "Привет, Джарвис."
    base = _profile()
    assert AudioAssetManager.cache_key(text, base) == AudioAssetManager.cache_key("Привет,   Джарвис.", base)
    assert AudioAssetManager.cache_key(text, base) != AudioAssetManager.cache_key(text, _profile(speed=1.1))
    assert AudioAssetManager.cache_key(text, base) != AudioAssetManager.cache_key(text, _profile("ru_RU-irina-medium"))


def test_asset_manager_saves_loads_cache_and_imports_prepared_wav(tmp_path):
    assets = AudioAssetManager(tmp_path / "assets", max_cache_bytes=2 * 1024 * 1024)
    samples = np.sin(np.linspace(0.0, 3.0, 2205, dtype=np.float32)) * 0.25
    cache_key = AudioAssetManager.cache_key("Тест", _profile())
    cached_path = assets.save_cached_audio(cache_key, samples, 22050)
    assert cached_path is not None and cached_path.is_file()
    assert assets.find_cached_audio(cache_key) == cached_path
    cached_audio, sample_rate = assets.load_audio(cached_path)
    assert sample_rate == 22050 and cached_audio.shape == samples.shape
    assert np.max(np.abs(cached_audio - samples)) < 0.0001

    prepared = assets.register_prepared_file("ru_RU-dmitri-medium", "router.launch.success", cached_path)
    assert assets.find_prepared_audio("ru_RU-dmitri-medium", "router.launch.success") == prepared
    prepared_audio, prepared_rate = assets.load_audio(prepared)
    assert prepared_rate == sample_rate and prepared_audio.shape == samples.shape


def test_asset_manager_cache_size_limit_and_key_validation(tmp_path):
    assets = AudioAssetManager(tmp_path / "assets", max_cache_bytes=3000)
    samples = np.full(1000, 0.2, dtype=np.float32)
    key_a = AudioAssetManager.cache_key("A", _profile())
    key_b = AudioAssetManager.cache_key("B", _profile())
    assets.save_cached_audio(key_a, samples, 22050)
    assets.save_cached_audio(key_b, samples, 22050)
    assert len(list(assets.cache_dir.glob("*.wav"))) <= 1
    with pytest.raises(ValueError, match="SHA-256"):
        assets.find_cached_audio("../../bad")


def test_tts_metrics_snapshot_tracks_counters_and_time():
    metrics = TTSMetrics()
    metrics.record_request()
    metrics.record_synthesis(0.25, success=True)
    metrics.record_cache_hit()
    metrics.record_prepared_hit()
    metrics.record_fallback()
    metrics.record_error()
    metrics.record_queue_rejection()
    snapshot = metrics.snapshot()
    assert snapshot.requests == snapshot.successful_syntheses == 1
    assert snapshot.synthesis_seconds_total == pytest.approx(0.25)
    assert snapshot.cache_hits == snapshot.prepared_audio_hits == 1
    assert snapshot.fallback_uses == snapshot.errors == snapshot.queue_rejections == 1


def test_speech_request_contract_rejects_unknown_cache_policy():
    assert SpeechRequest("Привет", response_key="greeting.hello").response_key == "greeting.hello"
    with pytest.raises(ValueError, match="cache_policy"):
        SpeechRequest("Привет", cache_policy="probably")
