"""Single source of truth for the JARVIS application version.

Keep the application version here so the updater, UI and future EXE build
configuration can use the same value.
"""

APP_NAME = "JARVIS"

# Semantic version of the current application build.
APP_VERSION = "0.1.0"


def get_version() -> str:
    """Return the current JARVIS application version."""
    return APP_VERSION
