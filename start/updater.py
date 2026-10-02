from __future__ import annotations

import argparse
import logging
from pathlib import Path
import subprocess
import sys
import time


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.update_install_policy import UpdateInstallPolicy
from services.update_installer import UpdateInstallError, UpdateInstaller


POLL_INTERVAL_SECONDS = 0.5
WAIT_TIMEOUT_SECONDS = 300.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JARVIS standalone updater")
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--expected-size", type=int, required=True)
    return parser.parse_args()


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False

    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        check=False,
    )
    output = result.stdout.strip()
    return bool(output) and str(pid) in output


def _wait_for_process_exit(pid: int, timeout: float = WAIT_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    while _is_process_running(pid):
        if time.monotonic() >= deadline:
            raise TimeoutError("JARVIS не завершился за отведённое время.")
        time.sleep(POLL_INTERVAL_SECONDS)


def _restart(application_root: Path) -> subprocess.Popen:
    bootstrap = application_root / "start" / "bootstrap.py"
    if not bootstrap.is_file():
        raise FileNotFoundError(f"Bootstrap JARVIS не найден: {bootstrap}")

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [sys.executable, str(bootstrap)],
        cwd=str(application_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
    )


def main() -> int:
    args = _parse_args()
    root = args.root.resolve()
    archive = args.archive.resolve()

    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "updater.log",
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        encoding="utf-8",
    )
    logger = logging.getLogger("jarvis.updater")

    try:
        logger.info("Updater started for PID %s", args.pid)
        _wait_for_process_exit(args.pid)

        policy = UpdateInstallPolicy(root)
        result = UpdateInstaller().install(
            archive,
            root,
            policy=policy,
            expected_size=args.expected_size,
        )
        logger.info("Update installed: %s files", result.installed_files)

        _restart(root)
        logger.info("JARVIS restart requested")
        return 0
    except (TimeoutError, FileNotFoundError, UpdateInstallError, OSError) as exc:
        logger.exception("Update failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
