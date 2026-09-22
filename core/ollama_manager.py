from __future__ import annotations

import logging
import subprocess
import time
import re

import requests
import psutil


logger = logging.getLogger("jarvis.ollama")


class OllamaManager:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self.process = None
        self.started_by_jarvis = False
        self.used_models: set[str] = set()
        logger.info("ollama_manager_created base_url=%s", self.base_url)

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        logger.info("ollama_base_url_changed base_url=%s", self.base_url)

    def is_running(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            logger.debug("ollama_health status=%s ok=%s", response.status_code, response.ok)
            return response.ok
        except requests.RequestException as exc:
            logger.debug("ollama_health failed error=%r", exc)
            return False

    def server_status(self) -> str:
        status = "запущен" if self.is_running() else "остановлен"
        logger.info("ollama_server_status status=%s", status)
        return status

    def register_model(self, model: str) -> None:
        if model:
            self.used_models.add(model)
            logger.debug("ollama_model_registered model=%s", model)

    def get_models(self) -> list[str]:
        if not self.is_running():
            return []
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            models = [item.get("name", "") for item in response.json().get("models", []) if item.get("name")]
            logger.info("ollama_models count=%d models=%r", len(models), models)
            return models
        except (requests.RequestException, ValueError):
            logger.exception("ollama_models_failed")
            return []

    def get_loaded_models(self) -> list[dict]:
        if not self.is_running():
            return []
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=2)
            response.raise_for_status()
            models = response.json().get("models", [])
            logger.info("ollama_loaded_models count=%d models=%r", len(models), models)
            return models
        except (requests.RequestException, ValueError):
            logger.exception("ollama_loaded_models_failed")
            return []

    def get_model_status(self, model: str):
        logger.debug("ollama_model_status model=%s", model)
        if not model or not self.is_running():
            return None
        for item in self.get_loaded_models():
            if item.get("name") == model or item.get("model") == model:
                return item
        return None

    def load_model(self, model: str) -> dict:
        logger.info("ollama_load_model_start model=%s", model)
        if not model:
            return {"success": False, "error": "Модель не указана."}
        if not self.is_running():
            return {"success": False, "error": "Ollama Server не запущен."}
        try:
            response = requests.post(f"{self.base_url}/api/generate", json={"model": model, "prompt": "", "stream": False, "keep_alive": -1}, timeout=(5, 600))
            logger.debug("ollama_load_model_response status=%s headers=%r body=%r", response.status_code, dict(response.headers), response.text)
            response.raise_for_status()
            self.register_model(model)
            result = {"success": True, "model": model, "status": self.get_model_status(model) is not None}
            logger.info("ollama_load_model_finish result=%r", result)
            return result
        except requests.RequestException as exc:
            logger.exception("ollama_load_model_failed model=%s", model)
            return {"success": False, "error": f"Не удалось загрузить модель: {exc}"}

    def unload_model(self, model: str) -> dict:
        logger.info("ollama_unload_model_start model=%s", model)
        if not model:
            return {"success": False, "error": "Модель не указана."}
        if not self.is_running():
            return {"success": False, "error": "Ollama Server не запущен."}
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
                timeout=30,
            )
            logger.debug(
                "ollama_unload_model_response status=%s headers=%r body=%r",
                response.status_code,
                dict(response.headers),
                response.text,
            )
            response.raise_for_status()

            # Ollama может принять keep_alive=0 раньше, чем модель исчезнет
            # из /api/ps. Не объявляем выгрузку успешной, пока это реально
            # не произошло.
            deadline = time.monotonic() + 10
            status = self.get_model_status(model)
            while status is not None and time.monotonic() < deadline:
                time.sleep(0.25)
                status = self.get_model_status(model)

            if status is not None:
                return {
                    "success": False,
                    "model": model,
                    "error": "Ollama приняла запрос, но модель всё ещё загружена.",
                }

            self.used_models.discard(model)
            result = {"success": True, "model": model, "status": False}
            logger.info("ollama_unload_model_finish result=%r", result)
            return result
        except requests.RequestException as exc:
            logger.exception("ollama_unload_model_failed model=%s", model)
            return {"success": False, "error": f"Не удалось выгрузить модель: {exc}"}

    def unload_models(self) -> list[dict]:
        logger.info("ollama_unload_models_start models=%r", list(self.used_models))
        results = [self.unload_model(model) for model in list(self.used_models)]
        self.used_models.clear()
        logger.info("ollama_unload_models_finish results=%r", results)
        return results

    def start(self, timeout=30):
        logger.info("ollama_start_requested timeout=%s", timeout)
        if self.is_running():
            self.started_by_jarvis = False
            logger.info("ollama_start_skipped already_running=True")
            return True
        try:
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
            self.started_by_jarvis = True
            logger.info("ollama_process_started pid=%s", self.process.pid)
        except FileNotFoundError as exc:
            logger.exception("ollama_executable_not_found")
            raise RuntimeError("Не удалось найти Ollama. Убедись, что Ollama установлена и доступна в PATH.") from exc
        except OSError as exc:
            logger.exception("ollama_process_start_failed")
            raise RuntimeError(f"Не удалось запустить Ollama: {exc}") from exc

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_running():
                logger.info("ollama_start_success pid=%s", self.process.pid if self.process else None)
                return True
            if self.process.poll() is not None:
                logger.error("ollama_process_exited_early returncode=%s", self.process.returncode)
                raise RuntimeError("Ollama завершилась сразу после запуска.")
            time.sleep(0.25)
        logger.error("ollama_start_timeout timeout=%s", timeout)
        raise RuntimeError(f"Ollama не успела запуститься за {timeout} секунд.")

    @staticmethod
    def _server_processes() -> list[psutil.Process]:
        """Находит все процессы Ollama Server независимо от того, кто их запустил."""
        result = []
        for process in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (process.info.get("name") or "").casefold()
                cmdline = " ".join(process.info.get("cmdline") or []).casefold()
                if name == "ollama.exe" and re.search(r"(?:^|\s)serve(?:\s|$)", cmdline):
                    result.append(process)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return result

    def stop_server(self) -> dict:
        """Останавливает Ollama Server независимо от способа его запуска."""
        logger.info("ollama_stop_requested started_by_jarvis=%s pid=%s", self.started_by_jarvis, self.process.pid if self.process else None)

        server_processes = self._server_processes()

        if self.process is not None:
            try:
                if self.process.poll() is None and all(process.pid != self.process.pid for process in server_processes):
                    server_processes.append(psutil.Process(self.process.pid))
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                pass

        if not server_processes:
            self.process = None
            self.started_by_jarvis = False
            if not self.is_running():
                return {"success": False, "error": "Процесс Ollama Server не найден."}
            return {"success": False, "error": "Ollama отвечает, но процесс Server не удалось определить."}

        errors = []
        for process in server_processes:
            try:
                logger.info("ollama_stop_terminate pid=%s", process.pid)
                process.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                errors.append(f"PID {process.pid}: {exc}")

        _, alive = psutil.wait_procs(server_processes, timeout=5)

        if alive:
            for process in alive:
                try:
                    logger.warning("ollama_stop_kill pid=%s", process.pid)
                    process.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied, OSError) as exc:
                    errors.append(f"PID {process.pid}: {exc}")

            _, alive = psutil.wait_procs(alive, timeout=3)

        self.process = None
        self.started_by_jarvis = False

        stopped = not self.is_running()
        if not stopped:
            errors.append("Ollama Server всё ещё отвечает на API.")

        result = {
            "success": stopped and not errors,
            "details": {
                "terminated_pids": [process.pid for process in server_processes],
                "still_alive": [process.pid for process in alive],
            },
        }
        if not result["success"]:
            result["error"] = "; ".join(errors) or "Не удалось остановить Ollama Server."
        logger.info("ollama_stop_finish result=%r", result)
        return result

    def shutdown_for_app(self) -> None:
        logger.info("ollama_shutdown_for_app")
        self.unload_models()
