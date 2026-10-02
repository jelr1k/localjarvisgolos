from __future__ import annotations

import logging
import random
from pathlib import PurePath


logger = logging.getLogger("jarvis.rofl")


class RoflService:
    """Редкие шуточные ответы после успешного запуска приложения или файла."""

    ROFL_CHANCE = 0.12
    DEMON_CHANCE = 0.15

    NORMAL_LINES = (
        "Готово, {target} открыта.",
        "Объект успешно призван.",
        "Открытие завершено. Жертва довольна.",
        "Портал в указанное приложение стабилизирован.",
        "Приложение материализовано.",
        "Дверь открыта. Не спрашивай, куда она ведёт.",
        "Porta interconnexa aperta est.",
        "Ritus invocationis perfectus est.",
        "Machina evocata est.",
        "Portal apertum est.",
        "Via inter mundos aperta est.",
    )

    DEMON_LINES = (
        "Ритуал завершён. Он уже здесь.",
        "Призыв завершён. Демон получил доступ к системе.",
        "Dæmon evocatus est.",
        "Ritus perfectus est. Porta aperta est.",
        "Invocatio daemonis completa est.",
        "Invocatio daemonis completa est. Quid fecisti?",
    )

    def __init__(self, event_bus):
        self.events = event_bus
        event_bus.subscribe("tool.executed", self._on_tool_executed)
        logger.debug(
            "rofl_service_created chance=%.2f demon_chance=%.2f",
            self.ROFL_CHANCE,
            self.DEMON_CHANCE,
        )

    @staticmethod
    def _display_target(arguments: dict, result: dict) -> str:
        target = str(arguments.get("target") or result.get("path") or "объект").strip().strip(""'")
        if not target:
            return "объект"
        if "/" in target or "\\" in target:
            name = PurePath(target.replace("\\", "/")).name
            if name:
                return name
        return target

    def _on_tool_executed(self, tool_name: str, arguments: dict, result: dict):
        if tool_name != "launch_application" or not result.get("success"):
            return
        if random.random() >= self.ROFL_CHANCE:
            return

        if random.random() < self.DEMON_CHANCE:
            text = random.choice(self.DEMON_LINES)
            category = "demon"
        else:
            text = random.choice(self.NORMAL_LINES).format(
                target=self._display_target(arguments, result)
            )
            category = "normal"

        logger.info(
            "rofl_response category=%s text=%r target=%r",
            category,
            text,
            arguments.get("target"),
        )
        self.events.emit("chat.rofl_response", text)

    def close(self):
        self.events.unsubscribe("tool.executed", self._on_tool_executed)
