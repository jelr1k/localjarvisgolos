from __future__ import annotations

import os
import re
import shutil
import unicodedata
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

_PENDING_LAUNCH_CHOICES: list[Path] = []


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


def _normalize_process_label(value: str | Path | None) -> str:
    """Нормализует имя процесса независимо от .exe, регистра и пунктуации."""
    text = str(value or "").strip().strip('"').replace("\\", "/")
    text = text.rsplit("/", 1)[-1]
    if text.casefold().endswith(".exe"):
        text = text[:-4]
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


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
    except Exception:  # COM can raise pywintypes.com_error as well as OSError.
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
            "executable_label": _normalize_process_label(executable),
        },
    )


def _process_cmdline_matches(cmdline: list[str] | None, executable: str | Path | None) -> bool:
    """Проверяет командную строку процесса на связь с целевым executable."""
    if not cmdline or not executable:
        return False

    target = _normalize_executable(executable)
    target_label = _normalize_process_label(executable)
    for argument in cmdline:
        argument_text = str(argument or "").strip().strip('"')
        if not argument_text:
            continue
        if _normalize_executable(argument_text) == target:
            return True
        if _normalize_process_label(argument_text) == target_label:
            return True
    return False


def _running_process_matches(name: str, *, executable: str | Path | None = None) -> list[dict]:
    """Find processes by stable executable identity, then by safe name fallbacks."""
    wanted_label = _normalize_process_label(name)
    executable_path = _normalize_executable(executable)
    executable_label = _normalize_process_label(executable) if executable else None
    result = []

    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            proc_name = proc.info.get("name") or ""
            proc_exe = proc.info.get("exe") or ""
            proc_cmdline = proc.info.get("cmdline") or []
            proc_normalized_exe = _normalize_executable(proc_exe)
            proc_label = _normalize_process_label(proc_name)
            proc_exe_label = _normalize_process_label(proc_exe)

            # If a shortcut target is known, it is the primary identity. This
            # works even when the Workspace name is unrelated to the process name.
            path_match = bool(executable_path and proc_normalized_exe == executable_path)
            executable_name_match = bool(executable_label and executable_label in {proc_label, proc_exe_label})
            cmdline_match = _process_cmdline_matches(proc_cmdline, executable) if executable else False

            # Only use the user's requested name when no executable identity is
            # available. This prevents a shortcut label from becoming the main
            # process identifier and accidentally matching an unrelated process.
            name_match = not executable and wanted_label in {proc_label, proc_exe_label}

            if path_match or executable_name_match or cmdline_match or name_match:
                result.append(
                    {
                        "pid": proc.info["pid"],
                        "name": proc_name,
                        "exe": proc_exe,
                        "cmdline": proc_cmdline,
                        "match": (
                            "executable_path"
                            if path_match
                            else "executable_name"
                            if executable_name_match
                            else "command_line"
                            if cmdline_match
                            else "process_name"
                        ),
                    }
                )
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    return result


def _select_process_roots(processes: list[psutil.Process]) -> list[psutil.Process]:
    """Keep only top-level matched processes when another matched process is their ancestor."""
    candidate_pids = {proc.pid for proc in processes}
    roots: list[psutil.Process] = []

    for proc in processes:
        try:
            has_matched_ancestor = any(parent.pid in candidate_pids for parent in proc.parents())
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            has_matched_ancestor = False
        if not has_matched_ancestor:
            roots.append(proc)

    return roots


def _collect_process_tree(root: psutil.Process) -> list[tuple[psutil.Process, int]]:
    """Collect root and all current descendants with their relative depth."""
    collected: list[tuple[psutil.Process, int]] = []
    seen: set[int] = set()

    def visit(proc: psutil.Process, depth: int) -> None:
        try:
            pid = proc.pid
            if pid in seen:
                return
            seen.add(pid)
            collected.append((proc, depth))
            for child in proc.children(recursive=False):
                visit(child, depth + 1)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            return

    visit(root, 0)
    return collected


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


def _selection_index(target: str) -> int | None:
    """Поддерживает выбор «первый», «второй», «1», «2» и т. п."""
    value = target.strip().lower().strip('"').rstrip(".")
    words = {
        "первый": 1, "первая": 1, "1": 1,
        "второй": 2, "вторая": 2, "2": 2,
        "третий": 3, "третья": 3, "3": 3,
        "четвёртый": 4, "четвертый": 4, "четвёртая": 4, "четвертая": 4, "4": 4,
        "пятый": 5, "пятая": 5, "5": 5,
    }
    return words.get(value)


def has_pending_launch_choices() -> bool:
    """Возвращает True, если Jarvis ждёт выбор файла для запуска."""
    return bool(_PENDING_LAUNCH_CHOICES)


def launch_application(target: str) -> dict:
    """Запускает файл из workspace или установленное приложение.

    Если предыдущая команда дала несколько вариантов, поддерживает выбор по номеру.
    """
    global _PENDING_LAUNCH_CHOICES

    try:
        target = validate_non_empty(target, "приложение или файл")
    except ValueError as exc:
        return _result(False, error=str(exc))

    index = _selection_index(target)
    if index is not None and _PENDING_LAUNCH_CHOICES:
        if index > len(_PENDING_LAUNCH_CHOICES):
            return _result(
                False,
                error=f"В списке только {len(_PENDING_LAUNCH_CHOICES)} вариант(а). Выбери номер от 1 до {len(_PENDING_LAUNCH_CHOICES)}.",
                ambiguous=True,
                matches=[str(path) for path in _PENDING_LAUNCH_CHOICES],
            )
        selected = _PENDING_LAUNCH_CHOICES[index - 1]
        _PENDING_LAUNCH_CHOICES = []
        return _start_path(selected)

    _PENDING_LAUNCH_CHOICES = []

    # Сначала проверяем workspace, чтобы одноимённый пользовательский файл
    # имел приоритет над приложением из Start Menu/PATH.
    file_path, matches = resolve_tool_path(target)
    if len(matches) > 1:
        _PENDING_LAUNCH_CHOICES = list(matches)
        numbered = "\n".join(f"{i}. {path}" for i, path in enumerate(matches, 1))
        return _result(
            False,
            error=("Найдено несколько файлов с таким именем. Какой запустить?\n" f"{numbered}\n\nВведите номер варианта."),
            ambiguous=True,
            matches=[str(p) for p in matches],
        )
    if file_path is not None:
        return _start_path(file_path)

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


def _resolve_close_identity(name: str) -> dict:
    """Разрешает имя приложения в identity, включая объекты из Workspace."""
    resolved = _resolve_application(name)
    if resolved.get("success"):
        return resolved

    # find_application ищет Start Menu/PATH, поэтому отдельно проверяем
    # Workspace. Это позволяет закрывать приложение даже если Jarvis его
    # запускал не сам и ярлык существует только внутри Workspace.
    workspace_path, workspace_matches = resolve_tool_path(name)
    if workspace_path is not None and len(workspace_matches) == 1:
        target = _resolve_shortcut_target(workspace_path)
        executable = target if target and target.suffix.lower() == ".exe" else (
            workspace_path if workspace_path.suffix.lower() == ".exe" else None
        )
        if executable is not None:
            return _result(
                True,
                path=workspace_path,
                identity={
                    "display_name": name,
                    "shortcut": str(workspace_path),
                    "target_executable": str(executable),
                    "normalized_executable": _normalize_executable(executable),
                    "executable_label": _normalize_process_label(executable),
                },
            )

    return resolved


def close_application(name: str) -> dict:
    try:
        name = validate_non_empty(name, "название приложения")
        resolved = _resolve_close_identity(name)

        if resolved.get("success"):
            identity = resolved["identity"]
            executable = identity.get("target_executable") or identity.get("normalized_executable")
            matches = _running_process_matches(name, executable=executable)
        else:
            matches = _running_process_matches(name)

        if not matches:
            return _result(True, running=False, already_closed=True, details={"closed": [], "failed": []})

        matched_processes = []
        failed = []
        for item in matches:
            try:
                matched_processes.append(psutil.Process(item["pid"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                failed.append({"pid": item["pid"], "error": str(exc)})

        roots = _select_process_roots(matched_processes)
        trees: dict[int, tuple[psutil.Process, int]] = {}
        for root in roots:
            for proc, depth in _collect_process_tree(root):
                existing = trees.get(proc.pid)
                if existing is None or depth > existing[1]:
                    trees[proc.pid] = (proc, depth)

        # Сначала закрываем потомков, затем корневой процесс. Это повторяет
        # поведение process-tree инструментов вроде taskkill /T, но оставляет
        # psutil полный контроль над PID и ожиданием завершения.
        processes = [proc for proc, _depth in sorted(trees.values(), key=lambda item: item[1], reverse=True)]
        for proc in processes:
            try:
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                failed.append({"pid": proc.pid, "error": str(exc)})

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
