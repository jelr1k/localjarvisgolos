from __future__ import annotations

import difflib
import json
import re
import unicodedata
from copy import deepcopy
from pathlib import Path

from core.app_paths import ALIASES_FILE, ensure_application_dirs


CATEGORIES = ("applications", "files", "folders", "actions")

DEFAULT_ACTION_ALIASES = {
    "launch": ["открой", "открыть", "запусти", "запустить", "включи", "включить"],
    "search": ["найди", "поищи", "покажи"],
    "delete": ["удали", "удалить", "стереть", "сотри"],
    "status": ["проверь", "проверить"],
}


class AliasError(ValueError):
    """Ошибка пользовательских алиасов."""


class AliasManager:
    """Хранилище и resolver пользовательских алиасов.

    Пользовательские данные живут отдельно от исходников в %APPDATA%/Jarvis.
    Exact-match безопасен и детерминирован; fuzzy-match только предлагает
    кандидат, а сохранение нового алиаса всегда требует явного подтверждения.
    """

    def __init__(self, path: str | Path | None = None):
        ensure_application_dirs()
        self.path = Path(path) if path else ALIASES_FILE
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    @staticmethod
    def _normalize_alias(value: str) -> str:
        text = unicodedata.normalize("NFKC", str(value)).strip().casefold()
        text = text.replace("ё", "е")
        text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
        return " ".join(text.split())

    @staticmethod
    def _normalize_target(value: str) -> str:
        text = unicodedata.normalize("NFKC", str(value)).strip().casefold().replace("ё", "е")
        text = text.replace("\\", "/")
        return re.sub(r"/+/", "/", text)

    @classmethod
    def _key(cls, category: str, value: str) -> str:
        if category == "actions":
            return cls._normalize_alias(value)
        return cls._normalize_target(value)

    @staticmethod
    def _default_data() -> dict:
        return {category: {} for category in CATEGORIES}

    def _load(self) -> dict:
        if not self.path.exists():
            data = self._default_data()
            try:
                self._save(data)
            except OSError:
                pass
            return data

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}

        merged = self._default_data()
        if isinstance(raw, dict):
            for category in CATEGORIES:
                section = raw.get(category)
                if isinstance(section, dict):
                    for target, value in section.items():
                        if isinstance(value, dict):
                            aliases = value.get("aliases", [])
                        else:
                            aliases = value
                        if not isinstance(aliases, list):
                            aliases = []
                        cleaned = []
                        seen = set()
                        for alias in aliases:
                            if not isinstance(alias, str):
                                continue
                            alias = alias.strip()
                            normalized = self._normalize_alias(alias)
                            if alias and normalized and normalized not in seen:
                                cleaned.append(alias)
                                seen.add(normalized)
                        merged[category][str(target)] = {"aliases": cleaned}
        return merged

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.path)

    def save(self) -> None:
        self._save(self.data)

    def list_objects(self, category: str | None = None) -> list[dict]:
        categories = [category] if category else list(CATEGORIES)
        result = []
        for current in categories:
            if current not in CATEGORIES:
                continue
            for target, entry in self.data[current].items():
                result.append({
                    "category": current,
                    "target": target,
                    "aliases": list(entry.get("aliases", [])),
                })
        return result

    def get_aliases(self, category: str, target: str) -> list[str]:
        entry = self.data.get(category, {}).get(target)
        return list(entry.get("aliases", [])) if entry else []

    def _find_conflict(self, category: str, alias: str, except_target: str | None = None) -> str | None:
        normalized = self._normalize_alias(alias)
        if not normalized:
            return None
        for target, entry in self.data.get(category, {}).items():
            if except_target is not None and target == except_target:
                continue
            if self._normalize_alias(target) == normalized:
                return target
            for existing in entry.get("aliases", []):
                if self._normalize_alias(existing) == normalized:
                    return target
        return None

    def set_aliases(self, category: str, target: str, aliases: list[str]) -> None:
        if category not in CATEGORIES:
            raise AliasError(f"Неизвестный тип алиаса: {category}")
        target = str(target).strip()
        if not target:
            raise AliasError("Целевой объект не может быть пустым.")

        cleaned = []
        seen = set()
        for alias in aliases:
            alias = str(alias).strip()
            normalized = self._normalize_alias(alias)
            if not alias or not normalized or normalized in seen:
                continue
            conflict = self._find_conflict(category, alias, except_target=target)
            if conflict:
                raise AliasError(f"Алиас «{alias}» уже привязан к «{conflict}».")
            cleaned.append(alias)
            seen.add(normalized)

        previous = deepcopy(self.data)
        self.data.setdefault(category, {})[target] = {"aliases": cleaned}
        try:
            self.save()
        except OSError:
            self.data = previous
            raise

    def add_alias(self, category: str, target: str, alias: str) -> None:
        aliases = self.get_aliases(category, target)
        aliases.append(alias)
        self.set_aliases(category, target, aliases)

    def remove_object(self, category: str, target: str) -> None:
        if category not in CATEGORIES:
            raise AliasError(f"Неизвестный тип алиаса: {category}")
        self.data.get(category, {}).pop(target, None)
        self.save()

    def resolve(self, category: str, query: str) -> dict:
        if category not in CATEGORIES:
            return {"status": "none"}
        query = str(query).strip()
        if not query:
            return {"status": "none"}

        normalized_alias = self._normalize_alias(query)
        normalized_target = self._normalize_target(query)
        exact = []
        for target, entry in self.data[category].items():
            if self._key(category, target) == (normalized_alias if category == "actions" else normalized_target):
                exact.append(target)
                continue
            if any(self._normalize_alias(alias) == normalized_alias for alias in entry.get("aliases", [])):
                exact.append(target)

        if len(exact) == 1:
            return {"status": "exact", "target": exact[0], "category": category}
        if len(exact) > 1:
            return {"status": "ambiguous", "candidates": exact, "category": category}
        return {"status": "none", "category": category}

    def suggest(self, category: str, query: str, limit: int = 5) -> list[dict]:
        if category not in CATEGORIES:
            return []
        normalized = self._normalize_alias(query)
        if not normalized:
            return []
        choices = []
        for target, entry in self.data[category].items():
            labels = [target, *entry.get("aliases", [])]
            best = max(
                (difflib.SequenceMatcher(None, normalized, self._normalize_alias(label)).ratio() for label in labels),
                default=0.0,
            )
            choices.append({"target": target, "category": category, "score": best})
        choices.sort(key=lambda item: item["score"], reverse=True)
        return [item for item in choices[:limit] if item["score"] >= 0.72]

    def resolve_any(self, query: str, categories: tuple[str, ...]) -> dict:
        exact = []
        for category in categories:
            result = self.resolve(category, query)
            if result["status"] == "exact":
                exact.append(result)
            elif result["status"] == "ambiguous":
                return result
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            return {
                "status": "ambiguous",
                "candidates": [f"{item['category']}: {item['target']}" for item in exact],
            }
        return {"status": "none"}

    def suggest_any(self, query: str, categories: tuple[str, ...], limit: int = 5) -> list[dict]:
        result = []
        for category in categories:
            result.extend(self.suggest(category, query, limit=limit))
        result.sort(key=lambda item: item["score"], reverse=True)
        return result[:limit]

    def resolve_tool_arguments(self, tool_name: str, arguments: dict) -> tuple[dict, dict | None]:
        """Подменяет пользовательское название на каноническое только при exact-match."""
        mapped = dict(arguments)
        queries = []
        if tool_name in {"find_application", "get_process_status", "close_application"} and "name" in mapped:
            queries = [("name", ("applications",))]
        elif tool_name == "launch_application" and "target" in mapped:
            queries = [("target", ("applications", "files", "folders"))]
        elif tool_name in {"read_file", "write_file", "delete_file", "rename_file", "copy_file", "move_file", "file_info"} and "path" in mapped:
            queries = [("path", ("files",))]
        elif tool_name == "search_files" and "name" in mapped:
            queries = [("name", ("files", "folders"))]

        for field, categories in queries:
            value = mapped.get(field)
            result = self.resolve_any(value, categories)
            if result["status"] == "exact":
                target = result["target"]
                if tool_name == "search_files":
                    target = Path(target).name
                mapped[field] = target
            elif result["status"] == "ambiguous":
                return mapped, result
        return mapped, None

    def default_aliases(self, category: str, target: str) -> list[str]:
        if category == "actions":
            return list(DEFAULT_ACTION_ALIASES.get(target, []))
        text = str(target).strip()
        normalized = self._normalize_alias(text)
        candidates = [text]
        if category == "applications":
            first = re.split(r"[\\s._-]+", text, maxsplit=1)[0]
            if first and self._normalize_alias(first) != normalized:
                candidates.append(first)
        else:
            basename = Path(text.replace("\\", "/")).name
            if basename and self._normalize_alias(basename) != normalized:
                candidates.append(basename)
        return candidates

    @classmethod
    def default_action_aliases(cls, action: str) -> list[str]:
        return list(DEFAULT_ACTION_ALIASES.get(action, []))

    def resolve_action(self, text: str) -> tuple[str, str] | None:
        normalized = " ".join(str(text).strip().split())
        if not normalized:
            return None
        aliases = []
        for action, defaults in DEFAULT_ACTION_ALIASES.items():
            aliases.extend((alias, action) for alias in defaults)
        for action, entry in self.data["actions"].items():
            aliases.extend((alias, action) for alias in entry.get("aliases", []))
        for alias, action in sorted(aliases, key=lambda item: len(item[0]), reverse=True):
            prefix = alias.strip()
            if not prefix:
                continue
            pattern = rf"^{re.escape(prefix)}(?:,)?\s+(.+)$"
            match = re.match(pattern, normalized, flags=re.IGNORECASE)
            if match:
                return action, match.group(1).strip()
        return None
