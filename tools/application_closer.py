from __future__ import annotations

"""Надёжное закрытие Windows-приложений по имени или ярлыку.

Модуль нужен как отдельный слой совместимости: основной модуль applications.py
может работать без pywin32, но Windows .lnk всё равно нужно уметь разрешать.
Для этого используется штатный WScript.Shell через PowerShell.
"""

import logging
import os
import shutil
import subprocess
import time
from pathlib import Path

import psutil

from tools import applications as _applications
from tools.paths import resolve_tool_path

logger = logging.getLogger("jarvis.process")


def _resolve_shortcut_with_windows_shell(path: Path) -> Path | None:
    """Разрешает .lnk без зависимости win32com/pywin32."""
    if path.suffix.lower() != ".lnk":
        return path

    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        logger.error("shortcut_resolve_failed path=%s reason=powershell_unavailable", path)
        return None

    command = (
        "$shell = New-Object -ComObject WScript.Shell; "
        "$shortcut = $shell.CreateShortcut($env:JARVIS_SHORTCUT); "
        "[Console]::Out.Write($shortcut.TargetPath)"
    )
    env = os.environ.copy()
    env["JARVIS_SHORTCUT"] = str(path)

    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=3,
            env=env,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.exception("shortcut_resolve_exception path=%s error=%r", path, exc)
        return None

    target = completed.stdout.strip().strip('"')
    if completed.returncode != 0 or not target:
        logger.error(
            "shortcut_resolve_failed path=%s returncode=%s stderr=%r",
            path,
            completed.returncode,
            completed.stderr.strip(),
        )
        return None

    target_path = Path(target)
    logger.info("shortcut_resolved_fallback path=%s target=%s", path, target_path)
    return target_path.resolve()


def _candidate_shortcuts(name: str) -> list[Path]:
    wanted = name.strip().strip('"')
    stem = Path(wanted).stem.casefold()
    candidates: set[Path] = set()

    workspace_path, workspace_matches = resolve_tool_path(wanted)
    if workspace_path is not None and len(workspace_matches) == 1:
        candidates.add(workspace_path.resolve())
    elif workspace_matches:
        candidates.update(Path(path).resolve() for path in workspace_matches)

    for root in _applications._WINDOWS_APP_DIRS:
        if not root.exists():
            continue
        try:
            for item in root.rglob("*.lnk"):
                if item.stem.casefold() == stem or item.name.casefold() == wanted.casefold():
                    candidates.add(item.resolve())
        except OSError:
            logger.exception("shortcut_scan_failed root=%s", root)

    return sorted(candidates, key=lambda path: str(path).casefold())


def _resolve_executable(name: str) -> tuple[Path | None, list[Path]]:
    """Использует тот же ApplicationResolver, что и остальные app-tools."""
    resolved = _applications._APPLICATION_RESOLVER.resolve(name, allow_workspace=True)
    if resolved.get("success"):
        identity = resolved.get("identity", {})
        executable = identity.get("target_executable") or identity.get("normalized_executable")
        if executable:
            sources = [Path(resolved["path"])] if resolved.get("path") else []
            logger.info("close_identity_unified name=%r executable=%s sources=%r", name, executable, sources)
            return Path(executable), sources

    matches = resolved.get("matches") or []
    return None, [Path(path) for path in matches]


def close_application(name: str) -> dict:
    """Закрывает только процессы, соответствующие реальному executable приложения."""
    started = time.perf_counter()
    logger.info("close_wrapper_start name=%r", name)

    try:
        executable, sources = _resolve_executable(name)
        if executable is None:
            if len(sources) > 1:
                return {
                    "success": False,
                    "error": "Не удалось однозначно определить исполняемый файл приложения.",
                    "ambiguous": True,
                    "matches": [str(path) for path in sources],
                }
            return {
                "success": False,
                "error": f"Не удалось определить исполняемый файл приложения: {name}",
                "matches": [str(path) for path in sources],
            }

        matches = _applications._running_process_matches(name, executable=str(executable))
        logger.info("close_wrapper_matches name=%r executable=%s matches=%r", name, executable, matches)
        if not matches:
            return {
                "success": True,
                "running": False,
                "already_closed": True,
                "details": {"closed": [], "failed": []},
            }

        matched_processes: list[psutil.Process] = []
        failed: list[dict] = []
        for item in matches:
            try:
                matched_processes.append(psutil.Process(item["pid"]))
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                failed.append({"pid": item.get("pid"), "error": str(exc)})

        roots = _applications._select_process_roots(matched_processes)
        tree: dict[int, tuple[psutil.Process, int]] = {}
        for root in roots:
            for proc, depth in _applications._collect_process_tree(root):
                tree.setdefault(proc.pid, (proc, depth))

        processes = [proc for proc, _depth in sorted(tree.values(), key=lambda item: item[1], reverse=True)]
        for proc in processes:
            try:
                logger.info("close_wrapper_terminate pid=%s", proc.pid)
                proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                failed.append({"pid": proc.pid, "error": str(exc)})

        gone, alive = psutil.wait_procs(processes, timeout=5)
        closed = [proc.pid for proc in gone]

        # Некоторые GUI-приложения игнорируют terminate(). Только процессы,
        # которые уже были подтверждены как принадлежащие приложению, можно
        # принудительно завершить после таймаута.
        if alive:
            for proc in alive:
                try:
                    logger.warning("close_wrapper_kill pid=%s", proc.pid)
                    proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                    failed.append({"pid": proc.pid, "error": str(exc)})
            gone_after_kill, alive_after_kill = psutil.wait_procs(alive, timeout=3)
            closed.extend(proc.pid for proc in gone_after_kill)
            alive = alive_after_kill

        success = not failed and not alive
        result = {
            "success": success,
            "running": bool(alive),
            "details": {"closed": closed, "failed": failed},
        }
        if not success:
            result["error"] = f"Не удалось полностью закрыть: {name}"
        logger.info("close_wrapper_finish name=%r executable=%s elapsed=%.4fs result=%r", name, executable, time.perf_counter() - started, result)
        return result
    except Exception:
        logger.exception("close_wrapper_unexpected_failure name=%r", name)
        return {"success": False, "error": f"Ошибка закрытия приложения: {name}"}
