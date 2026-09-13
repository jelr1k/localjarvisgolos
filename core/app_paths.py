from __future__ import annotations

import os
import sys
from pathlib import Path


def get_application_root() -> Path:
    """Возвращает каталог установки/размещения Jarvis.

    В исходниках это корень репозитория, в собранном приложении это каталог
    рядом с реально запущенным .exe. Путь не зависит от буквы диска.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def get_resource_root() -> Path:
    """Возвращает каталог ресурсов, включая поддержку PyInstaller."""
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        return Path(bundle_root).resolve()
    return get_application_root()


APP_ROOT = get_application_root()
RESOURCE_ROOT = get_resource_root()
WORKSPACE_DIR = APP_ROOT / "workspace"
LOG_DIR = APP_ROOT / "logs"
APP_DATA_DIR = Path(os.environ.get("APPDATA", APP_ROOT / "user_data")) / "Jarvis"
CONFIG_FILE = APP_DATA_DIR / "settings.json"
ALIASES_FILE = APP_DATA_DIR / "aliases.json"


def ensure_application_dirs() -> None:
    """Создаёт каталоги, которые нужны Jarvis во время работы."""
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)


def bundled_config_path() -> Path:
    return RESOURCE_ROOT / "config" / "settings.json"
