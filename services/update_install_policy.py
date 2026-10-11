"""Stage 12: define files and model caches that an update must preserve.

The policy is shared by the future installer and rollback logic. It describes
user-owned data separately from files that belong to the application package.
It does not copy, delete, install, or replace anything by itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path, PurePosixPath


@dataclass(frozen=True)
class ProtectedPath:
    """A path that must survive an application update."""

    path: Path
    reason: str
    external: bool = False


class UpdateInstallPolicy:
    """Describe user data and model locations that an installer must preserve."""

    def __init__(
        self,
        application_root: Path,
        *,
        app_data_dir: Path | None = None,
        environment: dict[str, str] | None = None,
        home_dir: Path | None = None,
    ):
        self.application_root = Path(application_root).resolve()
        if not self.application_root.is_dir():
            raise ValueError("Каталог приложения для политики обновления не найден.")

        env = os.environ if environment is None else environment
        home = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home().resolve()

        self.app_data_dir = (
            Path(app_data_dir).resolve()
            if app_data_dir is not None
            else Path(env.get("APPDATA", self.application_root / "user_data")).resolve() / "Jarvis"
        )

        self._protected = self._build_protected_paths(env, home)

    def protected_paths(self) -> tuple[ProtectedPath, ...]:
        """Return all known user-owned paths, including paths that do not exist yet."""
        return self._protected

    def protected_application_paths(self) -> tuple[Path, ...]:
        """Return protected paths located inside the application root."""
        return tuple(item.path for item in self._protected if not item.external)

    def protected_external_paths(self) -> tuple[Path, ...]:
        """Return protected paths outside the application root."""
        return tuple(item.path for item in self._protected if item.external)

    def is_protected(self, path: Path) -> bool:
        """Return whether a filesystem path belongs to protected user data."""
        candidate = Path(path).resolve()
        return any(
            candidate == item.path or item.path in candidate.parents
            for item in self._protected
        )

    def is_protected_archive_path(self, archive_path: str) -> bool:
        """Return whether a validated ZIP member targets protected app data."""
        try:
            relative = PurePosixPath(str(archive_path).replace("\\", "/"))
        except (TypeError, ValueError):
            return False

        if relative.is_absolute() or ".." in relative.parts:
            return False

        candidate = self.application_root.joinpath(*relative.parts).resolve()
        try:
            candidate.relative_to(self.application_root)
        except ValueError:
            return False
        return self.is_protected(candidate)

    def _build_protected_paths(
        self,
        environment: dict[str, str],
        home: Path,
    ) -> tuple[ProtectedPath, ...]:
        entries: list[ProtectedPath] = [
            ProtectedPath(self.application_root / "workspace", "рабочие файлы пользователя"),
            ProtectedPath(self.application_root / "logs", "логи пользователя"),
            ProtectedPath(self.application_root / "models", "локальные модели приложения"),
            ProtectedPath(self.app_data_dir, "пользовательские настройки и данные", external=True),
        ]

        hf_hub_cache = self._huggingface_cache(environment, home)
        if hf_hub_cache is not None:
            entries.append(
                ProtectedPath(hf_hub_cache, "кэш моделей Hugging Face", external=True)
            )

        ollama_models = self._ollama_models(environment, home)
        if ollama_models is not None:
            entries.append(
                ProtectedPath(ollama_models, "модели Ollama", external=True)
            )

        return self._deduplicate(entries)

    @staticmethod
    def _huggingface_cache(
        environment: dict[str, str],
        home: Path,
    ) -> Path | None:
        explicit_cache = environment.get("HF_HUB_CACHE", "").strip()
        if explicit_cache:
            return Path(explicit_cache).expanduser().resolve()

        hf_home = environment.get("HF_HOME", "").strip()
        if hf_home:
            return (Path(hf_home).expanduser() / "hub").resolve()

        return (home / ".cache" / "huggingface" / "hub").resolve()

    @staticmethod
    def _ollama_models(
        environment: dict[str, str],
        home: Path,
    ) -> Path | None:
        explicit_models = environment.get("OLLAMA_MODELS", "").strip()
        if explicit_models:
            return Path(explicit_models).expanduser().resolve()

        return (home / ".ollama" / "models").resolve()

    @staticmethod
    def _deduplicate(entries: list[ProtectedPath]) -> tuple[ProtectedPath, ...]:
        result: list[ProtectedPath] = []
        seen: set[Path] = set()
        for entry in entries:
            if entry.path in seen:
                continue
            seen.add(entry.path)
            result.append(entry)
        return tuple(result)
