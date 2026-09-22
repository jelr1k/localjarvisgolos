from __future__ import annotations

import logging
import subprocess
import time

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
            response = requests.post(f"{self.base_url}/api/generate", json={"model": model, "prompt": "", "stream": False, "keep_alive": 0}, timeout=10)
            logger.debug("ollama_unload_model_response status=%s headers=%r body=%r", response.status_code, dict(response.headers), response.text)
            response.raise_for_status()
            self.used_models.discard(model)
            result = {"success": True, "model": model, "status": self.get_model_status(model) is None}
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

    def stop_server(self) -> dict:
        logger.info("ollama_stop_requested started_by_jarvis=%s pid=%s", self.started_by_jarvis, self.process.pid if self.process else None)
        if not self.started_by_jarvis or self.process is None:
            # Ollama может быть запущена отдельно от Jarvis. В этом случае
            # собственного subprocess-хендла нет, поэтому ищем именно
            # процесс "ollama.exe serve", не трогая остальные процессы Ollama.
            server_processes = []
            for process in psutil.process_iter(["name", "cmdline"]):
                try:
                    name = (process.info.get("name") or "").casefold()
                    cmdline = " ".join(process.info.get("cmdline") or []).casefold()
                    if name == "ollama.exe" and "serve" in cmdline:
                        server_processes.append(process)
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue

            if not server_processes:
                return {"success": False, "error": "Процесс Ollama Server не найден."}

            errors = []
            for process in server_processes:
                try:
                    process.terminate()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                    errors.append(str(exc))

            _, alive = psutil.wait_procs(server_processes, timeout=5)
            for process in alive:
                try:
                    process.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                    errors.append(str(exc))

            if errors:
                logger.warning("ollama_external_stop_partial errors=%r", errors)
                return {"success": False, "error": f"Не удалось полностью остановить Ollama: {'; '.join(errors)}"}

            self.process = None
            self.started_by_jarvis = False
            logger.info("ollama_external_stop_success processes=%d", len(server_processes))
            return {"success": True}

        try:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
            self.process = None
            self.started_by_jarvis = False
            logger.info("ollama_stop_success forced=False")
            return {"success": True}
        except subprocess.TimeoutExpired:
            logger.warning("ollama_stop_timeout forcing_kill=True")
            try:
                self.process.kill()
                self.process.wait(timeout=3)
            finally:
                self.process = None
                self.started_by_jarvis = False
            return {"success": True, "details": {"forced": True}}
        except OSError as exc:
            logger.exception("ollama_stop_failed")
            return {"success": False, "error": f"Не удалось остановить Ollama: {exc}"}

    def shutdown_for_app(self) -> None:
        logger.info("ollama_shutdown_for_app")
        self.unload_models()
