class JarvisError(Exception):
    """Base exception for JARVIS."""

class LLMConnectionError(JarvisError):
    """Could not connect to an LLM backend."""

class LLMRequestError(JarvisError):
    """LLM request failed."""
