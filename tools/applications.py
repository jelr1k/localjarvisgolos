from __future__ import annotations

import logging
import os
import re
import shutil
import time
import unicodedata
from pathlib import Path

import psutil

from security.validator import validate_non_empty, validate_url
from tools.paths import resolve_tool_path

try:
    import win32com.client
except ImportError:  # pragma: no cover - Windows dependency
    win32com = None


logger = logging.getLogger("jarvis.process")

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
    text = str(value or "").strip().strip('"').replace("\\", "/")
    text = text.rsplit("/", 1)[-1]
    if text.casefold().endswith(".exe"):
        text = text[:-4]
    text = unicodedata.normalize("NFKC", text).casefold().replace("ё", "е")
    text = re.sub(r"[\W_]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def _resolve_shortcut_target(path: Path) -> Path | None:
    logger.debug("shortcut_resolve_start path=%s suffix=%s win32com=%s", path, path.suffix, win32com is not None)
    if path.suffix.lower() != ".lnk":
        return path
    if win32com is None:
        logger.error("shortcut_resolve_failed path=%s reason=win32com_unavailable", path)
        return None
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(str(path))
        target = (shortcut.TargetPath or "").strip()
        logger.info(
            "shortcut_resolved path=%s target=%s working_dir=%s arguments=%r",
            path,
            target,
            getattr(shortcut, "WorkingDirectory", ""),
            getattr(shortcut, "Arguments", ""),
        )
        if not target:
            return None
        return Path(target).resolve()
    except Exception:
        logger.exception("shortcut_resolve_exception path=%s", path)
        return None


def _application_identity(name: str, path: Path) -> dict:
    target = _resolve_shortcut_target(path)
    executable = target if target and target.suffix.lower() == ".exe" else (path if path.suffix.lower() == ".exe" else None)
    return {
        "display_name": name,
        "shortcut": str(path),
        "target_executable": str(target) if target else None,
        "normalized_executable": _normalize_executable(executable),
        "executable_label": _normalize_process_label(executable),
    }


class ApplicationResolver:
    """Единый resolver приложения: ярлык/Workspace -> реальный executable."""

    def resolve(self, name: str, *, allow_workspace: bool = False) -> dict:
        logger.info("application_resolver_start name=%r allow_workspace=%s", name, allow_workspace)
        found = find_application(name)
        if found.get("success"):
            shortcut = Path(found["path"])
            identity = _application_identity(name, shortcut)
            logger.info("application_resolver_installed name=%r identity=%r", name, identity)
            return _result(True, path=shortcut, identity=identity)

        if allow_workspace:
            workspace_path, workspace_matches = resolve_tool_path(name)
            logger.info(
                "application_resolver_workspace name=%r path=%r matches=%r",
                name, workspace_path, workspace_matches,
            )
            if workspace_path is not None and len(workspace_matches) == 1:
                target = _resolve_shortcut_target(workspace_path)
                executable = (
                    target if target and target.suffix.lower() == ".exe"
                    else workspace_path if workspace_path.suffix.lower() == ".exe"
                    else None
                )
                if executable is not None:
                    identity = {
                        "display_name": name,
                        "shortcut": str(workspace_path),
                        "target_executable": str(executable),
                        "normalized_executable": _normalize_executable(executable),
                        "executable_label": _normalize_process_label(executable),
                    }
                    return _result(True, path=workspace_path, identity=identity)

        return found


_APPLICATION_RESOLVER = ApplicationResolver()


def _resolve_application(name: str, *, allow_workspace: bool = False) -> dict:
    return _APPLICATION_RESOLVER.resolve(name, allow_workspace=allow_workspace)


def _process_cmdline_matches(cmdline: list[str] | None, executable: str | Path | None) -> bool:
    if not cmdline or not executable:
        return False
    target = _normalize_executable(executable)
    target_label = _normalize_process_label(executable)
    for argument in cmdline:
        argument_text = str(argument or "").strip().strip('"')
        if not argument_text:
            continue
        if _normalize_executable(argument_text) == target or _normalize_process_label(argument_text) == target_label:
            return True
    return False


def _process_snapshot(proc: psutil.Process) -> dict:
    try:
        info = proc.as_dict(attrs=["pid", "ppid", "name", "exe", "cmdline", "status", "username", "create_time"])
        return info
    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
        return {"pid": proc.pid, "error": str(exc)}


def _log_process_snapshot(reason: str) -> None:
    """Пишет полный доступный снимок процессов для диагностики."""
    snapshot = []
    try:
        for proc in psutil.process_iter(["pid", "ppid", "name", "exe", "cmdline", "status", "username", "create_time"]):
            try:
                snapshot.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue
        logger.debug("process_snapshot reason=%s count=%d processes=%r", reason, len(snapshot), snapshot)
    except Exception:
        logger.exception("process_snapshot_failed reason=%s", reason)


def _running_process_matches(name: str, *, executable: str | Path | None = None) -> list[dict]:
    logger.info("process_search_start requested_name=%r executable=%r", name, executable)
    wanted_label = _normalize_process_label(name)
    executable_path = _normalize_executable(executable)
    executable_label = _normalize_process_label(executable) if executable else None
    result = []

    for proc in psutil.process_iter(["pid", "ppid", "name", "exe", "cmdline", "status", "username", "create_time"]):
        try:
            proc_name = proc.info.get("name") or ""
            proc_exe = proc.info.get("exe") or ""
            proc_cmdline = proc.info.get("cmdline") or []
            proc_normalized_exe = _normalize_executable(proc_exe)
            proc_label = _normalize_process_label(proc_name)
            proc_exe_label = _normalize_process_label(proc_exe)
            path_match = bool(executable_path and proc_normalized_exe == executable_path)
            executable_name_match = bool(executable_label and executable_label in {proc_label, proc_exe_label})
            cmdline_match = _process_cmdline_matches(proc_cmdline, executable) if executable else False
            name_match = not executable and wanted_label in {proc_label, proc_exe_label}

            if path_match or executable_name_match or cmdline_match or name_match:
                item = dict(proc.info)
                item["match"] = "executable_path" if path_match else "executable_name" if executable_name_match else "command_line" if cmdline_match else "process_name"
                result.append(item)
                logger.info("process_match %r", item)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
            logger.debug("process_scan_skip error=%r", exc)

    logger.info("process_search_finish requested_name=%r matches=%d result=%r", name, len(result), result)
    return result


def _select_process_roots(processes: list[psutil.Process]) -> list[psutil.Process]:
    candidate_pids = {proc.pid for proc in processes}
    roots: list[psutil.Process] = []
    for proc in processes:
        try:
            parents = proc.parents()
            has_matched_ancestor = any(parent.pid in candidate_pids for parent in parents)
            logger.debug("process_root_check pid=%s matched_ancestor=%s parents=%s", proc.pid, has_matched_ancestor, [p.pid for p in parents])
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            has_matched_ancestor = False
        if not has_matched_ancestor:
            roots.append(proc)
    logger.info("process_roots roots=%s", [_process_snapshot(proc) for proc in roots])
    return roots


def _collect_process_tree(root: psutil.Process) -> list[tuple[psutil.Process, int]]:
    collected: list[tuple[psutil.Process, int]] = []
    seen: set[int] = set()

    def visit(proc: psutil.Process, depth: int) -> None:
        try:
            pid = proc.pid
            if pid in seen:
                return
            seen.add(pid)
            collected.append((proc, depth))
            logger.debug("process_tree_node pid=%s depth=%s info=%r", pid, depth, _process_snapshot(proc))
            for child in proc.children(recursive=False):
                visit(child, depth + 1)
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
            logger.debug("process_tree_skip error=%r", exc)

    visit(root, 0)
    logger.info("process_tree_collected root=%s nodes=%r", root.pid, [_process_snapshot(proc) for proc, _ in collected])
    return collected


def find_application(name: str) -> dict:
    try:
        raw = validate_non_empty(name, "название приложения")
    except ValueError as exc:
        logger.exception("find_application_validation_failed name=%r", name)
        return _result(False, error=str(exc))

    wanted = raw.lower().strip('"')
    stem = Path(wanted).stem
    candidates: list[Path] = []
    logger.info("find_application_start raw=%r wanted=%r stem=%r", raw, wanted, stem)

    for root in _WINDOWS_APP_DIRS:
        if not root.exists():
            logger.debug("find_application_root_missing root=%s", root)
            continue
        try:
            for item in root.rglob("*.lnk"):
                if item.stem.lower() == stem or item.name.lower() == wanted:
                    candidates.append(item.resolve())
                    logger.debug("find_application_candidate source=start_menu path=%s", item)
        except OSError:
            logger.exception("find_application_root_error root=%s", root)

    executable_name = wanted if wanted.endswith(".exe") else f"{wanted}.exe"
    path_match = shutil.which(executable_name)
    if path_match:
        candidates.append(Path(path_match).resolve())
        logger.debug("find_application_candidate source=PATH path=%s", path_match)

    unique = sorted(set(p for p in candidates if p.is_file()), key=lambda p: str(p).lower())
    logger.info("find_application_candidates raw=%r candidates=%r unique=%r", raw, candidates, unique)
    if not unique:
        return _result(False, error=f"Установленное приложение не найдено: {raw}", matches=[])

    # Несколько ярлыков одного приложения (например, системный и пользовательский
    # ярлык Steam) не должны считаться разными приложениями. Сначала разрешаем
    # .lnk в реальные exe и группируем кандидатов по исполняемому файлу.
    executable_groups: dict[str, list[Path]] = {}
    unresolved: list[Path] = []
    for candidate in unique:
        target = _resolve_shortcut_target(candidate)
        executable = target if target and target.suffix.lower() == ".exe" else (candidate if candidate.suffix.lower() == ".exe" else None)
        normalized = _normalize_executable(executable)
        if normalized:
            executable_groups.setdefault(normalized, []).append(candidate)
        else:
            unresolved.append(candidate)

    if len(executable_groups) == 1:
        group_paths = next(iter(executable_groups.values()))
        selected = group_paths[0]
        logger.info("find_application_deduplicated raw=%r executable=%r paths=%r", raw, next(iter(executable_groups)), group_paths)
        return _result(True, path=selected, matches=[str(p) for p in group_paths])

    # Если определить цель ярлыков не удалось, оставляем старое поведение:
    # неоднозначность безопаснее, чем закрыть не то приложение.
    if len(unique) > 1:
        return _result(False, error="Найдено несколько вариантов приложения.", ambiguous=True, matches=[str(p) for p in unique])

    return _result(True, path=unique[0], matches=[str(unique[0])])


def get_process_status(name: str) -> dict:
    logger.info("process_status_start name=%r", name)
    try:
        name = validate_non_empty(name, "название приложения")
        resolved = _resolve_application(name)
        if resolved.get("success"):
            identity = resolved["identity"]
            matches = _running_process_matches(name, executable=identity.get("normalized_executable"))
        else:
            matches = _running_process_matches(name)
        result = _result(True, running=bool(matches), processes=matches)
        logger.info("process_status_finish name=%r result=%r", name, result)
        return result
    except ValueError as exc:
        logger.exception("process_status_validation_failed name=%r", name)
        return _result(False, error=str(exc))


def _selection_index(target: str) -> int | None:
    value = target.strip().lower().strip('"').rstrip(".")
    words = {"первый": 1, "первая": 1, "1": 1, "второй": 2, "вторая": 2, "2": 2, "третий": 3, "третья": 3, "3": 3, "четвёртый": 4, "четвертый": 4, "четвёртая": 4, "четвертая": 4, "4": 4, "пятый": 5, "пятая": 5, "5": 5}
    return words.get(value)


def has_pending_launch_choices() -> bool:
    return bool(_PENDING_LAUNCH_CHOICES)



def _workspace_launch_denial(target: str, *, reason: str | None = None) -> dict:
    message = (
        "Доступ запрещён: объект находится вне Workspace. "
        "В режиме «Только Workspace» запуск внешних файлов и приложений запрещён."
    )
    if reason:
        message += f" {reason}"
    logger.warning("launch_blocked_outside_workspace target=%r reason=%s", target, reason)
    return _result(False, error=message, blocked=True, outside_workspace=True)


def _is_outside_workspace_path(target: str) -> bool:
    try:
        from security.sandbox import is_inside_sandbox
        path = Path(target).expanduser()
        if not path.is_absolute() and not any(separator in target for separator in ("\\", "/", ":")):
            return False
        if not path.exists():
            return False
        return not is_inside_sandbox(path, allow_nonexistent=False)
    except (OSError, ValueError):
        return False


def launch_application(target: str, allow_outside_workspace: bool = False) -> dict:
    global _PENDING_LAUNCH_CHOICES
    logger.info("launch_start target=%r", target)
    try:
        target = validate_non_empty(target, "приложение или файл")
    except ValueError as exc:
        return _result(False, error=str(exc))

    index = _selection_index(target)
    if index is not None and _PENDING_LAUNCH_CHOICES:
        logger.info("launch_pending_choice index=%s choices=%r", index, _PENDING_LAUNCH_CHOICES)
        if index > len(_PENDING_LAUNCH_CHOICES):
            return _result(False, error=f"В списке только {len(_PENDING_LAUNCH_CHOICES)} вариант(а). Выбери номер от 1 до {len(_PENDING_LAUNCH_CHOICES)}.", ambiguous=True, matches=[str(path) for path in _PENDING_LAUNCH_CHOICES])
        selected = _PENDING_LAUNCH_CHOICES[index - 1]
        _PENDING_LAUNCH_CHOICES = []
        return _start_path(selected)

    _PENDING_LAUNCH_CHOICES = []
    if not allow_outside_workspace and _is_outside_workspace_path(target):
        return _workspace_launch_denial(target)

    file_path, matches = resolve_tool_path(target)
    logger.info("launch_workspace_resolution target=%r file_path=%r matches=%r", target, file_path, matches)
    if len(matches) > 1:
        _PENDING_LAUNCH_CHOICES = list(matches)
        numbered = "\n".join(f"{i}. {path}" for i, path in enumerate(matches, 1))
        return _result(False, error="Найдено несколько файлов с таким именем. Какой запустить?\n" f"{numbered}\n\nВведите номер варианта.", ambiguous=True, matches=[str(p) for p in matches])
    if file_path is not None:
        return _start_path(file_path)

    found = find_application(target)
    if found.get("success"):
        found_path = Path(found["path"])
        if not allow_outside_workspace:
            return _workspace_launch_denial(
                target,
                reason=f"Найдено приложение по адресу: {found_path}",
            )
        return _start_path(found_path)

    return _result(False, error=found.get("error") or f"Файл или приложение не найдено: {target}")


def _start_path(path: Path) -> dict:
    logger.info("launch_path_start path=%s", path)
    try:
        if not path.exists():
            return _result(False, path=path, error="Указанный объект не существует.")
        os.startfile(str(path))
        logger.info("launch_path_success path=%s", path)
        return _result(True, path=path, details={"started": True})
    except OSError as exc:
        logger.exception("launch_path_failed path=%s", path)
        return _result(False, path=path, error=f"Не удалось запустить: {exc}")


def _resolve_close_identity(name: str) -> dict:
    return _APPLICATION_RESOLVER.resolve(name, allow_workspace=True)


def close_application(name: str) -> dict:
    started = time.perf_counter()
    logger.info("close_start name=%r", name)
    _log_process_snapshot("before_close")
    try:
        name = validate_non_empty(name, "название приложения")
        resolved = _resolve_close_identity(name)
        logger.info("close_resolved name=%r result=%r", name, resolved)

        if resolved.get("success"):
            identity = resolved["identity"]
            executable = identity.get("target_executable") or identity.get("normalized_executable")
            matches = _running_process_matches(name, executable=executable)
        else:
            matches = _running_process_matches(name)

        logger.info("close_matches name=%r matches=%r", name, matches)
        if not matches:
            result = _result(True, running=False, already_closed=True, details={"closed": [], "failed": []})
            logger.info("close_finish name=%r elapsed=%.4fs result=%r", name, time.perf_counter() - started, result)
            return result

        matched_processes = []
        failed = []
        for item in matches:
            try:
                proc = psutil.Process(item["pid"])
                matched_processes.append(proc)
                logger.info("close_candidate pid=%s info=%r match=%s", proc.pid, _process_snapshot(proc), item.get("match"))
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                failed.append({"pid": item["pid"], "error": str(exc)})
                logger.exception("close_candidate_failed pid=%s", item.get("pid"))

        roots = _select_process_roots(matched_processes)
        trees: dict[int, tuple[psutil.Process, int]] = {}
        for root in roots:
            for proc, depth in _collect_process_tree(root):
                existing = trees.get(proc.pid)
                if existing is None or depth > existing[1]:
                    trees[proc.pid] = (proc, depth)

        processes = [proc for proc, _depth in sorted(trees.values(), key=lambda item: item[1], reverse=True)]
        logger.info("close_process_order processes=%r", [_process_snapshot(proc) for proc in processes])
        for proc in processes:
            try:
                logger.info("close_terminate pid=%s info_before=%r", proc.pid, _process_snapshot(proc))
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                failed.append({"pid": proc.pid, "error": str(exc)})
                logger.exception("close_terminate_failed pid=%s", proc.pid)

        gone, alive = psutil.wait_procs(processes, timeout=5)
        closed = [proc.pid for proc in gone]
        for proc in alive:
            failed.append({"pid": proc.pid, "error": "Процесс не завершился за отведённое время."})
            logger.warning("close_process_alive_after_wait pid=%s info=%r", proc.pid, _process_snapshot(proc))

        _log_process_snapshot("after_close")
        success = not failed and not alive
        result = _result(success, running=bool(alive), details={"closed": closed, "failed": failed}, error=None if success else f"Не удалось полностью закрыть: {name}")
        logger.info("close_finish name=%r elapsed=%.4fs result=%r", name, time.perf_counter() - started, result)
        return result
    except ValueError as exc:
        logger.exception("close_validation_failed name=%r", name)
        return _result(False, error=str(exc))
    except Exception:
        logger.exception("close_unexpected_failure name=%r", name)
        raise


def open_url(url: str) -> dict:
    logger.info("open_url_start url=%r", url)
    try:
        url = validate_url(url)
        os.startfile(url)
        logger.info("open_url_success url=%r", url)
        return _result(True, details={"url": url})
    except (ValueError, OSError) as exc:
        logger.exception("open_url_failed url=%r", url)
        return _result(False, error=f"Не удалось открыть URL: {exc}")
