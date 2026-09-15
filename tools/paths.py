from __future__ import annotations

import difflib
import os
import re
import shutil
from pathlib import Path

from core.app_paths import APP_ROOT, WORKSPACE_DIR, ensure_application_dirs
from security.sandbox import SandboxError, is_inside_sandbox, resolve_inside_sandbox

TOOL_WORKSPACE = WORKSPACE_DIR
SEARCH_ROOTS = (TOOL_WORKSPACE, APP_ROOT)
SKIPPED_SEARCH_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", "logs"}

_CYRILLIC_TO_LATIN = str.maketrans({
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "j", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
})
_FILENAME_SEPARATOR_RE = re.compile(r"[\s_.-]+")
_VOWELS_RE = re.compile(r"[aeiouy]+")
_FUZZY_FILENAME_THRESHOLD = 0.78


def _search_roots() -> tuple[Path, ...]:
    return (TOOL_WORKSPACE, APP_ROOT)


def prepare_tool_workspace() -> Path:
    ensure_application_dirs()
    legacy_workspace = APP_ROOT / "test"
    if not TOOL_WORKSPACE.exists() and legacy_workspace.exists():
        try:
            legacy_workspace.rename(TOOL_WORKSPACE)
        except OSError:
            pass
    TOOL_WORKSPACE.mkdir(parents=True, exist_ok=True)
    return TOOL_WORKSPACE.resolve()


def is_path_allowed(path: Path) -> bool:
    return is_inside_sandbox(path, allow_nonexistent=True)


def is_readable_search_path(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False
    if not resolved.is_file():
        return False
    for root in _search_roots():
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _clean_name(name: str) -> str:
    return str(name or "").strip().strip('"')


def _matches_name(path: Path, name: str) -> bool:
    wanted = _clean_name(name).lower()
    if not wanted:
        return False
    if path.name.lower() == wanted:
        return True
    return path.stem.lower() == Path(wanted).stem.lower()


def _filename_key(value: str) -> str:
    transliterated = value.casefold().translate(_CYRILLIC_TO_LATIN)
    return _VOWELS_RE.sub("a", transliterated)


def _filename_tokens(value: str) -> list[str]:
    return [token for token in _FILENAME_SEPARATOR_RE.split(_filename_key(value)) if token]


def _fuzzy_filename_score(path: Path, name: str) -> float:
    wanted = _filename_tokens(name)
    candidate = _filename_tokens(path.name)
    if not wanted or not candidate:
        return 0.0

    token_scores = []
    for wanted_token in wanted:
        token_scores.append(
            max(
                difflib.SequenceMatcher(None, wanted_token, candidate_token).ratio()
                for candidate_token in candidate
            )
        )

    score = sum(token_scores) / len(token_scores)
    if len(wanted) == len(candidate):
        score += 0.03
    if _filename_key(path.stem) == _filename_key(Path(name).stem):
        score = max(score, 0.98)
    return min(score, 1.0)


def _iter_search_files(root: Path):
    root = root.resolve()
    if not root.exists():
        return
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = [directory for directory in dirs if directory not in SKIPPED_SEARCH_DIRS]
        current_path = Path(current)
        for filename in files:
            yield current_path / filename


def find_by_name(name: str, extension: str | None = None, *, fuzzy: bool = False) -> list[Path]:
    prepare_tool_workspace()
    name = _clean_name(name)
    extension = (extension or "").strip()
    if extension and not extension.startswith("."):
        extension = "." + extension
    if not name:
        return []

    matches: list[Path] = []
    seen: set[Path] = set()
    for root in _search_roots():
        for path in _iter_search_files(root) or ():
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                continue
            if not resolved.is_file() or resolved in seen:
                continue
            if root.resolve() == TOOL_WORKSPACE.resolve() and not is_path_allowed(resolved):
                continue
            if extension and resolved.suffix.lower() != extension.lower():
                continue
            if _matches_name(resolved, name):
                seen.add(resolved)
                matches.append(resolved)

    if matches or not fuzzy:
        return sorted(matches, key=lambda item: str(item).lower())

    fuzzy_matches: list[tuple[float, Path]] = []
    for root in _search_roots():
        for path in _iter_search_files(root) or ():
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                continue
            if not resolved.is_file() or resolved in seen:
                continue
            if root.resolve() == TOOL_WORKSPACE.resolve() and not is_path_allowed(resolved):
                continue
            if extension and resolved.suffix.lower() != extension.lower():
                continue
            score = _fuzzy_filename_score(resolved, name)
            if score >= _FUZZY_FILENAME_THRESHOLD:
                fuzzy_matches.append((score, resolved))

    if not fuzzy_matches:
        return []

    fuzzy_matches.sort(key=lambda item: (-item[0], str(item[1]).lower()))
    best_score = fuzzy_matches[0][0]
    return [path for score, path in fuzzy_matches if score >= best_score - 0.03]


def resolve_tool_path(value: str) -> tuple[Path | None, list[Path]]:
    raw = _clean_name(value)
    if not raw:
        return None, []

    prepare_tool_workspace()
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            resolved = resolve_inside_sandbox(candidate, allow_nonexistent=False)
            return (resolved, [resolved]) if resolved.is_file() else (None, [])
        except SandboxError:
            return None, []

    try:
        relative = resolve_inside_sandbox(candidate, allow_nonexistent=False)
        if relative.is_file():
            return relative, [relative]
    except SandboxError:
        pass

    matches = find_by_name(raw)
    matches = [match for match in matches if is_path_allowed(match)]
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def resolve_read_path(value: str) -> tuple[Path | None, list[Path]]:
    raw = _clean_name(value)
    if not raw:
        return None, []

    prepare_tool_workspace()
    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        try:
            resolved = candidate.resolve(strict=True)
        except OSError:
            return None, []
        return (resolved, [resolved]) if is_readable_search_path(resolved) else (None, [])

    try:
        workspace_candidate = resolve_inside_sandbox(candidate, allow_nonexistent=False)
        if workspace_candidate.is_file():
            return workspace_candidate, [workspace_candidate]
    except SandboxError:
        pass

    matches = find_by_name(raw)
    if len(matches) == 1:
        return matches[0], matches
    return None, matches


def resolve_tool_target(value: str) -> Path:
    prepare_tool_workspace()
    return resolve_inside_sandbox(_clean_name(value), allow_nonexistent=True)


def add_file_to_workspace(source: str | Path) -> Path:
    source_path = Path(source).expanduser()
    if not source_path.exists() or not source_path.is_file():
        raise ValueError("Можно добавить только существующий файл.")

    target = resolve_inside_sandbox(source_path.name, allow_nonexistent=True)
    if target.exists():
        raise FileExistsError(f"Файл уже существует в Workspace: {target.name}")

    try:
        shutil.copy2(source_path, target)
    except OSError as exc:
        raise OSError(f"Не удалось добавить файл в Workspace: {exc}") from exc
    return target
