from __future__ import annotations

import os
import shutil
from pathlib import Path

import psutil

from security.validator import validate_non_empty, validate_url
from tools.paths import resolve_tool_path

_WINDOWS_APP_DIRS = [
    Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
]


def _result(success: bool, *, path=None, error=None, **extra):
    data = {"success": success}
    if path is not None:
        data["path"] = str(path)
    if error:
        data["error"] = error
    data.update(extra)
    return data


def _running_process_matches(name: str) -> list[dict]:
    wanted = name.lower().strip()
    result = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            proc_name = (proc.info.get("name") or "").lower()
            exe = proc.info.get("exe") or ""
            stem = Path(exe).stem.lower() if exe else Path(proc_name).stem
            if wanted in {proc_name, stem} or wanted == Path(proc_name).stem:
                result.append({"pid": proc.info["pid"], "name": proc.info.get("name"), "exe": exe})
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return result


def find_application(name: str) -> dict:
    """Ищет установленное приложение через Start Menu и PATH."""
    try:
        raw = validate_non_empty(name, "название приложения")
    except ValueError as exc:
        return _result(False, error=str(exc))

    wanted = raw.lower().strip('"')
    stem = Path(wanted).stem
    candidates: list[Path] = []

    for root in _WINDOWS_APP_DIRS:
        if not root.exists():
            continue
        try:
            for item in root.rglob("*.lnk"):
                if item.stem.lower() == stem or item.name.lower() == wanted:
                    candidates.append(item.resolve())
        except OSError:
            continue

    executable_name = wanted if wanted.endswith(".exe") else f"{wanted}.exe"
    path_match = shutil.which(executable_name)
    if path_match:
        candidates.append(Path(path_match).resolve())

    unique = sorted(set(p for p in candidates if p.is_file()), key=lambda p: str(p).lower())
    if not unique:
        return _result(False, error=f"Установленное приложение не найдено: {raw}", matches=[])
    if len(unique) > 1:
        return _result(False, error="Найдено несколько вариантов приложения.", ambiguous=True, matches=[str(p) for p in unique])
    return _result(True, path=unique[0], matches=[str(unique[0])])


def get_process_status(name: str) -> dict:
    try:
        name = validate_non_empty(name, "название процесса")
        matches = _running_process_matches(name)
        return _result(True, running=bool(matches), processes=matches)
    except ValueError as exc:
        return _result(False, error=str(exc))


def launch_application(target: str) -> dict:
    """Запускает установленное приложение или файл из sandbox, без shell."""
    try:
        target = validate_non_empty(target, "приложение или файл")
    except ValueError as exc:
        return _result(False, error=str(exc))

    found = find_application(target)
    if found.get("success"):
        return _start_path(Path(found["path"]))

    file_path, matches = resolve_tool_path(target)
    if len(matches) > 1:
        return _result(False, error="Найдено несколько файлов с таким именем.", ambiguous=True, matches=[str(p) for p in matches])
    if file_path is None:
        return _result(False, error=found.get("error") or f"Файл не найден: {target}")
    return _start_path(file_path)


def _start_path(path: Path) -> dict:
    try:
        if not path.is_file():
            return _result(False, path=path, error="Указанный объект не является файлом.")
        os.startfile(str(path))
        return _result(True, path=path, details={"started": True})
    except OSError as exc:
        return _result(False, path=path, error=f"Не удалось запустить: {exc}")


def close_application(name: str) -> dict:
    try:
        name = validate_non_empty(name, "название процесса")
        matches = _running_process_matches(name)
        if not matches:
            return _result(False, error=f"Процесс не запущен: {name}", running=False)
        closed = []
        failed = []
        for item in matches:
            try:
                proc = psutil.Process(item["pid"])
                proc.terminate()
                closed.append(item["pid"])
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                failed.append({"pid": item["pid"], "error": str(exc)})
        return _result(not failed, details={"closed": closed, "failed": failed})
    except ValueError as exc:
        return _result(False, error=str(exc))


def open_url(url: str) -> dict:
    try:
        url = validate_url(url)
        os.startfile(url)
        return _result(True, details={"url": url})
    except (ValueError, OSError) as exc:
        return _result(False, error=f"Не удалось открыть URL: {exc}")
