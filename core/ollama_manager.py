from __future__ import annotations

import subprocess
import time

import requests


class OllamaManager:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self.process = None
        self.started_by_jarvis = False
        self.used_models: set[str] = set()

    def set_base_url(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def is_running(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            return response.ok
        except requests.RequestException:
            return False

    def server_status(self) -> str:
        return "запущен" if self.is_running() else "остановлен"

    def register_model(self, model: str) -> None:
        if model:
            self.used_models.add(model)

    def get_models(self) -> list[str]:
        if not self.is_running():
            return []
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            return [item.get("name", "") for item in response.json().get("models", []) if item.get("name")]
        except (requests.RequestException, ValueError):
            return []

    def get_loaded_models(self) -> list[dict]:
        if not self.is_running():
            return []
        try:
            response = requests.get(f"{self.base_url}/api/ps", timeout=2)
            response.raise_for_status()
            return response.json().get("models", [])
        except (requests.RequestException, ValueError):
            return []

    def get_model_status(self, model: str):
        if not model or not self.is_running():
            return None
        for item in self.get_loaded_models():
            if item.get("name") == model or item.get("model") == model:
                return item
        return None

    def load_model(self, model: str) -> dict:
        if not model:
            return {"success": False, "error": "Модель не указана."}
        if not self.is_running():
            return {"success": False, "error": "Ollama Server не запущен."}
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": "", "stream": False, "keep_alive": -1},
                timeout=(5, 600),
            )
            response.raise_for_status()
            self.register_model(model)
            return {"success": True, "model": model, "status": self.get_model_status(model) is not None}
        except requests.RequestException as exc:
            return {"success": False, "error": f"Не удалось загрузить модель: {exc}"}

    def unload_model(self, model: str) -> dict:
        if not model:
            return {"success": False, "error": "Модель не указана."}
        if not self.is_running():
            return {"success": False, "error": "Ollama Server не запущен."}
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": "", "stream": False, "keep_alive": 0},
                timeout=10,
            )
            response.raise_for_status()
            self.used_models.discard(model)
            return {"success": True, "model": model, "status": self.get_model_status(model) is None}
        except requests.RequestException as exc:
            return {"success": False, "error": f"Не удалось выгрузить модель: {exc}"}

    def unload_models(self) -> list[dict]:
        results = [self.unload_model(model) for model in list(self.used_models)]
        self.used_models.clear()
        return results

    def start(self, timeout=30):
        if self.is_running():
            self.started_by_jarvis = False
            return True
        try:
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            self.started_by_jarvis = True
        except FileNotFoundError as exc:
            raise RuntimeError("Не удалось найти Ollama. Убедись, что Ollama установлена и доступна в PATH.") from exc
        except OSError as exc:
            raise RuntimeError(f"Не удалось запустить Ollama: {exc}") from exc

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_running():
                return True
            if self.process.poll() is not None:
                raise RuntimeError("Ollama завершилась сразу после запуска.")
            time.sleep(0.25)
        raise RuntimeError(f"Ollama не успела запуститься за {timeout} секунд.")

    def stop_server(self) -> dict:
        """Останавливает только сервер, запущенный самим Jarvis."""
        if not self.started_by_jarvis or self.process is None:
            return {"success": False, "error": "Ollama запущена не Jarvis или процесс запуска неизвестен."}
        try:
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
            self.process = None
            self.started_by_jarvis = False
            return {"success": True}
        except subprocess.TimeoutExpired:
            try:
                self.process.kill()
                self.process.wait(timeout=3)
            finally:
                self.process = None
                self.started_by_jarvis = False
            return {"success": True, "details": {"forced": True}}
        except OSError as exc:
            return {"success": False, "error": f"Не удалось остановить Ollama: {exc}"}

    def shutdown_for_app(self) -> None:
        # При закрытии Jarvis сервер не трогаем. Освобождаем только модели.
        self.unload_models()
