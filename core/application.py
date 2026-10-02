from __future__ import annotations

import logging

from core.alias_manager import AliasManager
from core.app_paths import ensure_application_dirs
from core.config_manager import ConfigManager
from core.dependency_manager import get_dependency_manager
from core.events import EventBus
from core.ollama_manager import OllamaManager
from core.task_runner import TaskRunner
from security.permissions import PermissionManager
from llm.ollama import OllamaProvider
from services.chat_service import ChatService
from services.rofl_service import RoflService
from tools.paths import prepare_tool_workspace
from voice.controller import VoiceService
from voice.wake_word import WakeWordDetector


logger = logging.getLogger("jarvis.application")


class JarvisApplication:
    """Framework-independent Jarvis backend.

    It owns application services and lifecycle. A frontend creates the visual
    shell and connects to EventBus through a presentation adapter.
    """

    def __init__(self):
        logger.info("backend_application_init_start")
        ensure_application_dirs()
        prepare_tool_workspace()

        self.events = EventBus()
        self.tasks = TaskRunner(max_workers=4)
        self.rofl_service = RoflService(self.events)
        self.config = ConfigManager()
        self.alias_manager = AliasManager()
        self.ollama_manager = OllamaManager(self.config.ollama_url)
        self.provider = OllamaProvider(self.config.ollama_url)
        self.dependency_manager = get_dependency_manager(self.events)
        self.permission_manager = PermissionManager(self.config)
        self.chat_service = ChatService(
            self.provider,
            self.config,
            self.ollama_manager,
            self.alias_manager,
            permission_manager=self.permission_manager,
            event_bus=self.events,
            task_runner=self.tasks,
        )
        self.voice_service = VoiceService(
            self.config,
            event_bus=self.events,
            task_runner=self.tasks,
        )
        self.wake_word_detector = WakeWordDetector(
            self.config,
            event_bus=self.events,
        )
        self.ollama_manager.register_model(self.config.get("model"))
        self._started = False
        self._shutdown_started = False
        logger.info("backend_application_init_finish model=%s", self.config.get("model"))

    def set_ui_actions(self, actions: dict | None):
        """Register abstract window actions supplied by the active frontend."""
        self.chat_service.set_ui_actions(actions)

    def start(self):
        if self._started or self._shutdown_started:
            return
        self._started = True

        def start_ollama():
            try:
                return self.ollama_manager.start()
            except Exception as exc:
                logger.warning("ollama_start_at_boot_failed error=%s", exc)
                return {"success": False, "error": str(exc)}

        future = self.tasks.submit(start_ollama)
        future.add_done_callback(lambda f: self.events.emit(
            "application.ollama_start_finished",
            f.result() if not f.exception() else {"success": False, "error": str(f.exception())},
        ))

        if self.config.get("voice", {}).get("wake_word_enabled", True):
            self.wake_word_detector.start()

        self.events.emit("application.started")

    def apply_settings(self):
        """Apply persisted settings to backend services."""
        self.provider.set_base_url(self.config.ollama_url)
        self.ollama_manager.set_base_url(self.config.ollama_url)
        self.voice_service.apply_config(self.config)
        self.wake_word_detector.apply_config(self.config)
        self.ollama_manager.register_model(self.config.get("model"))
        if self.config.get("voice", {}).get("wake_word_enabled", True):
            self.wake_word_detector.restart()
        else:
            self.wake_word_detector.stop()
        self.events.emit(
            "application.settings_applied",
            self.config.get("model"),
            self.config.get("assistant_name", "JARVIS"),
        )

    def shutdown(self):
        if self._shutdown_started:
            return
        self._shutdown_started = True
        logger.info("backend_application_shutdown_start")

        try:
            self.rofl_service.close()
        except Exception:
            logger.exception("rofl_service_close_failed")
        try:
            self.wake_word_detector.close()
        except Exception:
            logger.exception("wake_word_close_failed")
        try:
            self.voice_service.close()
        except Exception:
            logger.exception("voice_close_failed")
        try:
            self.chat_service.shutdown()
        except Exception:
            logger.exception("chat_shutdown_failed")
        try:
            self.ollama_manager.shutdown_for_app()
        except Exception:
            logger.exception("ollama_shutdown_failed")

        self.events.emit("application.stopped")
        self.tasks.shutdown(wait=False, cancel_futures=True)
        logger.info("backend_application_shutdown_finish")
