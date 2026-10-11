"""Local voice output API; imports remain backwards compatible."""
from .asset_manager import AudioAssetManager
from .audio_player import AudioPlayer, SoundDevicePlayer
from .engine import TTSBackend
from .engines.piper import (DEFAULT_TTS_SPEED, DEFAULT_TTS_VOLUME, DEFAULT_TTS_VOICE,
                            MAX_VOICE_FILE_BYTES, SUPPORTED_TTS_VOICES, PiperTTSBackend)
from .errors import TTSConfigurationError, TTSError, TTSVoiceNotInstalledError
from .metrics import TTSMetrics, TTSMetricsSnapshot
from .models import SpeechRequest, VoiceProfile
from .service import TTSService
from .text import MAX_SPEECH_CHARS, SPEECH_CHUNK_CHARS, prepare_speech_text, split_speech_text
from .voice_manager import VoiceManager

__all__ = [
    "AudioAssetManager", "AudioPlayer", "DEFAULT_TTS_SPEED", "DEFAULT_TTS_VOLUME", "DEFAULT_TTS_VOICE",
    "MAX_SPEECH_CHARS", "MAX_VOICE_FILE_BYTES", "PiperTTSBackend", "SUPPORTED_TTS_VOICES",
    "SPEECH_CHUNK_CHARS", "SoundDevicePlayer", "SpeechRequest", "TTSBackend", "TTSConfigurationError",
    "TTSMetrics", "TTSMetricsSnapshot", "TTSService", "TTSError", "TTSVoiceNotInstalledError",
    "VoiceManager", "VoiceProfile", "prepare_speech_text", "split_speech_text",
]
