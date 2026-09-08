import subprocess
import time

import requests


class OllamaManager:

    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self.process = None
        self.started_by_jarvis = False

        # Модели, которые использовал JARVIS
        self.used_models = set()

    def is_running(self):
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=1.5
            )

            return response.ok

        except requests.RequestException:
            return False

    def register_model(self, model):
        """
        Запоминаем модель, которую использовал JARVIS.
        """
        if model:
            self.used_models.add(model)

    def get_model_status(self, model):
        """
        Получает информацию о загруженной модели из Ollama /api/ps.
        """

        if not model:
            return None

        try:
            response = requests.get(
                f"{self.base_url}/api/ps",
                timeout=2
            )

            response.raise_for_status()

            models = response.json().get("models", [])

            for item in models:
                if (
                    item.get("name") == model
                    or item.get("model") == model
                ):
                    return item

            return None

        except requests.RequestException:
            return None

    def unload_model(self, model):
        """
        Выгружает конкретную модель из памяти Ollama.
        """

        if not model:
            return

        if not self.is_running():
            return

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "",
                    "stream": False,
                    "keep_alive": 0,
                },
                timeout=10,
            )

            response.raise_for_status()

        except requests.RequestException:
            # При закрытии приложения не падаем из-за ошибки выгрузки.
            pass

    def unload_models(self):
        """
        Выгружает все модели, которые использовал JARVIS.
        """

        for model in list(self.used_models):
            self.unload_model(model)

        self.used_models.clear()

    def start(self, timeout=30):
        # Ollama уже запущена
        if self.is_running():
            return True

        try:
            creation_flags = 0

            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creation_flags = subprocess.CREATE_NO_WINDOW

            self.process = subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation_flags,
            )

            self.started_by_jarvis = True

        except FileNotFoundError as exc:
            raise RuntimeError(
                "Не удалось найти Ollama.\n\n"
                "Убедись, что Ollama установлена и команда "
                "'ollama' доступна из PATH."
            ) from exc

        except OSError as exc:
            raise RuntimeError(
                f"Не удалось запустить Ollama:\n{exc}"
            ) from exc

        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:

            if self.is_running():
                return True

            if self.process.poll() is not None:
                raise RuntimeError(
                    "Ollama завершилась сразу после запуска."
                )

            time.sleep(0.25)

        raise RuntimeError(
            "Ollama не успела запуститься за "
            f"{timeout} секунд."
        )

    def stop(self):
        """
        Корректно завершает работу JARVIS с Ollama.
        """

        # Сначала выгружаем использованные модели.
        self.unload_models()

        # Если Ollama была запущена до JARVIS,
        # сервер оставляем работать.
        if not self.started_by_jarvis:
            return

        if self.process is None:
            return

        if self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)

            except subprocess.TimeoutExpired:
                self.process.kill()

        self.process = None
        self.started_by_jarvis = False
