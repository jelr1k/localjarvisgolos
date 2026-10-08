from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Any

from core.alias_manager import AliasManager

logger = logging.getLogger("jarvis.target_resolver")


class TargetResolver:
    """Разрешает объект из естественной фразы, не превращая всю фразу в алиас."""

    _TOKEN_RE = re.compile(r"[^\s]+")
    _TRIM_CHARS = " ,:;.!?\"'«»()[]{}"

    def __init__(self, alias_manager: AliasManager, workspace_index_getter: Callable[[], Any] | None = None):
        self.alias_manager = alias_manager
        self.workspace_index_getter = workspace_index_getter

    @classmethod
    def _fragments(cls, query: str) -> list[str]:
        tokens = cls._TOKEN_RE.findall(" ".join(str(query).strip().split()))
        result: list[str] = []
        seen: set[str] = set()
        # Longest spans first. This makes "мой Google Chrome" resolve to
        # "Google Chrome", while still handling one-word names such as Steam.
        for size in range(len(tokens), 0, -1):
            for start in range(len(tokens) - size + 1):
                fragment = " ".join(tokens[start:start + size]).strip(cls._TRIM_CHARS)
                if not fragment or fragment in seen:
                    continue
                seen.add(fragment)
                result.append(fragment)
        return result

    def _resolve_exact(self, query: str, categories: tuple[str, ...], use_workspace_index: bool) -> dict:
        if use_workspace_index and self.workspace_index_getter is not None:
            entry, matches = self.workspace_index_getter().resolve(
                query, categories, self.alias_manager, fuzzy=False
            )
            if entry is not None:
                return {"status": "exact", "target": str(entry.path), "category": entry.category, "source": "workspace"}
            if len(matches) > 1:
                return {
                    "status": "ambiguous",
                    "candidates": [str(item.path) for item in matches],
                    "source": "workspace",
                }

        result = self.alias_manager.resolve_any(query, categories)
        if result.get("status") in {"exact", "ambiguous"}:
            result = dict(result)
            result["source"] = "alias"
        return result

    def resolve(self, query: str, categories: tuple[str, ...], *, alias_confirmation_callback=None, use_workspace_index: bool = False):
        normalized = " ".join(str(query).strip().split())
        logger.debug("target_resolve_start query=%r categories=%r workspace_index=%s", normalized, categories, use_workspace_index)
        if not normalized:
            return query, None

        fragments = self._fragments(normalized)
        ambiguous: dict | None = None
        for fragment in fragments:
            result = self._resolve_exact(fragment, categories, use_workspace_index)
            if result.get("status") == "exact":
                logger.info(
                    "target_resolved query=%r matched=%r target=%r source=%s",
                    normalized, fragment, result.get("target"), result.get("source"),
                )
                return result["target"], None
            if result.get("status") == "ambiguous":
                ambiguous = result

        # Preserve the old fuzzy/confirmation behavior, but only after all
        # exact fragments have been checked. The whole natural-language phrase
        # is no longer saved as an alias just because it contains a known name.
        if ambiguous is not None:
            candidates = [str(item) for item in ambiguous.get("candidates", [])[:5]]
            message = "Не удалось однозначно определить объект."
            if candidates:
                message += " Варианты: " + "; ".join(candidates)
            return None, message

        suggestions = self.alias_manager.suggest_any(normalized, categories, limit=5)
        if not suggestions:
            return query, None
        if len(suggestions) > 1 and suggestions[0]["score"] - suggestions[1]["score"] < 0.08:
            items = [item["target"] for item in suggestions[:5]]
            return None, "Не удалось однозначно определить объект. Варианты: " + "; ".join(items)
        suggestion = suggestions[0]
        if alias_confirmation_callback is None:
            return query, None
        accepted = alias_confirmation_callback(normalized, suggestion["target"], suggestion["category"])
        if not accepted:
            return query, None
        self.alias_manager.add_alias(suggestion["category"], suggestion["target"], normalized)
        return suggestion["target"], None
