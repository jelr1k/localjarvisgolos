import json
from pathlib import Path
from copy import deepcopy


DEFAULTS = {
    "assistant_name": "JARVIS",
    "model": "qwen3-1.7b-no-think:latest",
    "thinking": False,
    "temperature": 0.7,
    "context_length": 32768,
    "max_tokens": 4096,
    "ollama": {
        "base_url": "http://localhost:11434"
    },
}


class ConfigManager:
    def __init__(self, path="config/settings.json"):
        self.path = Path(path)

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.data = self._load()

    def _load(self):
        if not self.path.exists():
            self._save(DEFAULTS)
            return deepcopy(DEFAULTS)

        try:
            data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

        except (OSError, json.JSONDecodeError):
            data = deepcopy(DEFAULTS)

        merged = deepcopy(DEFAULTS)

        self._merge(
            merged,
            data
        )

        return merged

    @staticmethod
    def _merge(target, source):
        for key, value in source.items():

            if (
                isinstance(value, dict)
                and isinstance(
                    target.get(key),
                    dict
                )
            ):
                ConfigManager._merge(
                    target[key],
                    value
                )

            else:
                target[key] = value

    def _save(self, data):
        self.path.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2
            ),
            encoding="utf-8"
        )

    def save(self):
        self._save(self.data)

    def get(self, key, default=None):
        return self.data.get(
            key,
            default
        )

    def set(self, key, value):
        self.data[key] = value
        self.save()

    @property
    def ollama_url(self):
        return self.data["ollama"]["base_url"]
