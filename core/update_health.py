"""Startup health handshake used by the separate updater process."""

from __future__ import annotations

import json
import os
from pathlib import Path
import uuid


UPDATE_HEALTH_ENV = "JARVIS_UPDATE_HEALTH_FILE"


def write_startup_health_marker(version: str) -> bool:
    """Atomically report that the UI and application controller started.

    Returns False during an ordinary launch where no updater requested a
    handshake. The marker is written only when the caller reaches its ready
    point, never merely because Python was able to create a process.
    """
    raw_path = os.environ.get(UPDATE_HEALTH_ENV, "").strip()
    if not raw_path:
        return False

    target = Path(raw_path).expanduser().resolve()
    if target.is_symlink() or (target.exists() and not target.is_file()):
        raise OSError("Файл подтверждения запуска небезопасен.")

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(
            json.dumps({"status": "ready", "version": str(version)}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
    return True
