# TTS package

This package is the local voice-output boundary for Jarvis. Keep ChatService, Router, RoflService, and UI code independent from a concrete TTS engine.

- `service.py`: EventBus subscription, bounded request queue, worker lifecycle, status and error handling.
- `engine.py`: backend contract shared by Piper and future engines.
- `engines/piper.py`: current local Piper backend.
- `text.py` and `audio_player.py`: text cleanup and serialized playback.
- `voice_manager.py`: persistent voice profiles and active profile.
- `asset_manager.py`: stable prepared-WAV assets and a size-bounded synthesis cache.
- `metrics.py`: service counters and synthesis timings.

Prepared audio, bounded cache, and voice-profile storage are implemented. `TTSService` resolves a matching prepared WAV (response key first, then normalized text), then an exact synthesis-cache entry, and otherwise performs live synthesis. Unreadable prepared/cache entries fall back to synthesis; synthesis failures are reported while the text response remains usable. A separately configurable secondary TTS engine fallback is not implemented.

Voice-profile reference audio is metadata for a future cloning-capable engine. Piper cannot clone a voice from an arbitrary sample. Audio import currently supports uncompressed 16-bit PCM WAV (mono/stereo); convert other formats before import.
