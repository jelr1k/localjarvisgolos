# TTS package

This package is the local voice-output boundary for Jarvis. Keep ChatService, Router, RoflService, and UI code independent from a concrete TTS engine.

- `service.py`: EventBus subscription, bounded request queue, worker lifecycle, status and error handling.
- `engine.py`: backend contract shared by Piper and future engines.
- `engines/piper.py`: current local Piper backend.
- `text.py` and `audio_player.py`: text cleanup and serialized playback.
- `voice_manager.py`: persistent voice profiles and active profile.
- `asset_manager.py`: stable prepared-WAV assets and a size-bounded synthesis cache.
- `metrics.py`: service counters and synthesis timings.

Prepared audio/cache storage and profile management are independently implemented and tested, but not yet connected to the live playback routing. The next stage will pass optional `response_key` values through speech events and resolve: prepared WAV → exact generated-audio cache → live synthesis → configured fallback. Until then, do not treat cache hits or prepared-file playback as active behavior in the UI.

Voice-profile reference audio is metadata for a future cloning-capable engine. Piper cannot clone a voice from an arbitrary sample. Audio import currently supports uncompressed 16-bit PCM WAV (mono/stereo); convert other formats before import.
