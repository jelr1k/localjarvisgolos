from __future__ import annotations

import os
import shutil
from pathlib import Path

import psutil

from security.validator import validate_non_empty, validate_url
from tools.paths import resolve_tool_path

try:
    import win32com.client
except ImportError:  # pragma: no cover - Windows dependency
    win32com = None

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


def _normalize_executable(path: str | Path | None) -> str | None:
    if not path:
        return None
    try:
        return str(Path(path).resolve()).lower()
    except (OSError, RuntimeError):
        return os.path.normcase(os.path.abspath(str(path)))


def _resolve_shortcut_target(path: Path) -> Path | None:
    """Resolve a Windows .lnk into its target executable."""
    if path.suffix.lower() != ".lnk":
        return path
    if win32com is None:
        return None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(path))
        target = (shortcut.TargetPath or "").strip()
        if not target:
            return None
        return Path(target).resolve()
    except (OSError, RuntimeError, AttributeError):
        return None


def _resolve_application(name: str) -> dict:
    """Resolve display name/path into a stable application identity."""
    found = find_application(name)
    if not found.get("success"):
        return found

    shortcut = Path(found["path"])
    target = _resolve_shortcut_target(shortcut)
    executable = target if target and target.suffix.lower() == ".exe" else (shortcut if shortcut.suffix.lower() == ".exe" else None)

    return _result(
        True,
        path=shortcut,
        identity={
            "display_name": name,
            "shortcut": str(shortcut),
            "target_executable": str(target) if target else None,
            "normalized_executable": _normalize_executable(executable),
        },
    )


def _running_process_matches(name: str, *, executable: str | Path | None = None) -> list[dict]:
    """Find processes by resolved executable, with display-name fallback."""
    wanted = name.lower().strip()
    normalized_executable = _normalize_executable(executable)
    wanted_stem = Path(wanted).stem
    result = []

    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            proc_name = (proc.info.get("name") or "").lower()
            proc_exe = proc.info.get("exe") or ""
            proc_normalized_exe = _normalize_executable(proc_exe)
            proc_stem = Path(proc_exe).stem.lower() if proc_exe else Path(proc_name).stem.lower()

            if normalized_executable:
                matches = proc_normalized_exe == normalized_executable or proc_stem == Path(normalized_executable).stem.lower()
            else:
                matches = wanted in {proc_name, proc_stem} or wanted_stem == Path(proc_name).stem.lower()

            if matches:
                result.append({"pid": proc.info["pid"], "name": proc.info.get("name"), "exe": proc_exe})
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
        name = validate_non_empty(name, "название приложения")
        resolved = _resolve_application(name)
        if resolved.get("success"):
            identity = resolved["identity"]
            matches = _running_process_matches(name, executable=identity.get("normalized_executable"))
        else:
            matches = _running_process_matches(name)
        return _result(True, running=bool(matches), processes=matches)
    except ValueError as exc:
        return _result(False, error=str(exc))


def launch_application(target: str) -> dict:
    """Запускает любой существующий файл из workspace или установленное приложение."""
    try:
        target = validate_non_empty(target, "приложение или файл")
    except ValueError as exc:
        return _result(False, error=str(exc))

    # Сначала проверяем workspace. Это гарантирует, что файл пользователя
    # имеет приоритет над одноимённым приложением из Start Menu/PATH.
    file_path, matches = resolve_tool_path(target)
    if len(matches) > 1:
        return _result(False, error="Найдено несколько файлов с таким именем.", ambiguous=True, matches=[str(p) for p in matches])
    if file_path is not None:
        return _start_path(file_path)

    # Если в workspace ничего не найдено, ищем обычное установленное приложение.
    found = find_application(target)
    if found.get("success"):
        return _start_path(Path(found["path"]))

    return _result(False, error=found.get("error") or f"Файл или приложение не найдено: {target}")


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
        name = validate_non_empty(name, "название приложения")
        resolved = _resolve_application(name)
        if resolved.get("success"):
            identity = resolved["identity"]
            matches = _running_process_matches(name, executable=identity.get("normalized_executable"))
        else:
            matches = _running_process_matches(name)

        if not matches:
            return _result(True, running=False, already_closed=True, details={"closed": [], "failed": []})

        processes = []
        failed = []
        for item in matches:
            try:
                processes.append(psutil.Process(item["pid"]))
                processes[-1].terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                failed.append({"pid": item["pid"], "error": str(exc)})

        gone, alive = psutil.wait_procs(processes, timeout=5)
        closed = [proc.pid for proc in gone]
        for proc in alive:
            failed.append({"pid": proc.pid, "error": "Процесс не завершился за отведённое время."})

        success = not failed and not alive
        return _result(
            success,
            running=bool(alive),
            details={"closed": closed, "failed": failed},
            error=None if success else f"Не удалось полностью закрыть: {name}",
        )
    except ValueError as exc:
        return _result(False, error=str(exc))


def open_url(url: str) -> dict:
    try:
        url = validate_url(url)
        os.startfile(url)
        return _result(True, details={"url": url})
    except (ValueError, OSError) as exc:
        return _result(False, error=f"Не удалось открыть URL: {exc}")
