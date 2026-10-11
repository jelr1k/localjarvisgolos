"""Public exceptions raised by the TTS subsystem."""

class TTSError(RuntimeError):
    """Base exception for text-to-speech failures."""


class TTSVoiceNotInstalledError(TTSError):
    """Raised when the configured voice model has not been downloaded yet."""


class TTSConfigurationError(TTSError):
    """Raised when the selected voice or synthesis parameters are invalid."""
