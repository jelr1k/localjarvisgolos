from __future__ import annotations

import logging
import threading

import numpy as np
import sounddevice as sd

from voice.command_normalizer import normalize_voice_command
from voice.devices import find_input_device_by_name, find_supported_sample_rate, list_input_devices, _normalize_name
from voice.microphone import MicrophoneRecorder
from voice.speech_recognizer import SpeechRecognizer
from core.task_runner import TaskRunner


logger = logging.getLogger("jarvis.voice")


class VoiceService:
    """Backend voice controller. GUI/framework code is intentionally absent."""

    def __init__(self, config: dict, event_bus=None, task_runner: TaskRunner | None = None):
        self.events = event_bus
        self.tasks = task_runner or TaskRunner(max_workers=2)
        self._silence_stop = threading.Event()
        self._silence_thread: threading.Thread | None = None
        self._transcription_future = None
        self.recorder: MicrophoneRecorder | None = None
        self.recognizer: SpeechRecognizer | None = None
        self.apply_config(config)

    def _emit(self, event: str, *args):
        if self.events is not None:
            self.events.emit(event, *args)

    def apply_config(self, config: dict):
        voice_config = config.get("voice", {})
        self.sample_rate = int(voice_config.get("sample_rate", 16000))
        self.channels = int(voice_config.get("channels", 1))
        self.silence_duration = max(0.5, float(voice_config.get("silence_duration", 2.0)))
        configured_device = voice_config.get("input_device")
        configured_name = voice_config.get("input_device_name")
        self._configured_device = configured_device
        self._configured_device_name = configured_name

        self.device = configured_device
        if configured_name:
            resolved = find_input_device_by_name(configured_name)
            if resolved is not None:
                self.device = int(resolved["index"])

        self.model_name = voice_config.get("model", "small")
        self.device_type = voice_config.get("device", "cpu")
        self.compute_type = voice_config.get("compute_type", "int8")
        self.cpu_threads = max(1, int(voice_config.get("cpu_threads", 4)))
        self.beam_size = max(1, int(voice_config.get("beam_size", 5)))
        self.language = voice_config.get("language", "ru")
        self.min_duration = float(voice_config.get("min_duration", 0.25))

        if self.recorder is not None and self.recorder.is_recording:
            self._silence_stop.set()
            self.recorder.stop()
            self._emit("voice.listening_changed", False)

        self.recorder = None
        self.recording_sample_rate = self.sample_rate
        try:
            self.recording_sample_rate = find_supported_sample_rate(
                device=self.device,
                channels=self.channels,
                preferred=self.sample_rate,
            )
            self.recorder = MicrophoneRecorder(
                sample_rate=self.recording_sample_rate,
                channels=self.channels,
                device=self.device,
            )
        except Exception as exc:
            logger.warning("voice_microphone_unavailable device=%r error=%r", self.device, exc)

        recognizer_config_matches = (
            self.recognizer is not None
            and self.recognizer.model_name == self.model_name
            and self.recognizer.device == self.device_type
            and self.recognizer.compute_type == self.compute_type
            and self.recognizer.language == self.language
            and self.recognizer.cpu_threads == self.cpu_threads
        )
        if recognizer_config_matches:
            self.recognizer.update_settings(beam_size=self.beam_size)
        else:
            if self.recognizer is not None:
                unload_stats = self.recognizer.close()
                if unload_stats is not None:
                    self._emit("voice.whisper_stats", unload_stats)
            self.recognizer = SpeechRecognizer(
                model_name=self.model_name,
                device=self.device_type,
                compute_type=self.compute_type,
                language=self.language,
                cpu_threads=self.cpu_threads,
                beam_size=self.beam_size,
            )

    def list_microphones(self):
        """Return available input devices and the currently selected device."""
        try:
            devices = list(sd.query_devices())
            hostapis = list(sd.query_hostapis())
            current_name = self._configured_device_name
            current_index = self._configured_device
            result = [{
                "index": None,
                "name": "Системный микрофон по умолчанию",
                "hostapi_name": "",
                "selected": current_index is None and not current_name,
            }]
            normalized = _normalize_name(current_name or "")
            for device in list_input_devices(devices, hostapis):
                index = int(device["index"])
                name = str(device.get("name", f"Микрофон {index}"))
                selected = (
                    bool(normalized and _normalize_name(name) == normalized)
                    or (not current_name and current_index == index)
                )
                result.append({
                    "index": index,
                    "name": name,
                    "hostapi_name": str(device.get("hostapi_name", "")),
                    "selected": selected,
                })
            if not any(item["selected"] for item in result):
                result[0]["selected"] = True
            return {"success": True, "devices": result}
        except Exception as exc:
            return {"success": False, "error": str(exc), "devices": []}

    def test_microphone(self, device):
        """Record a short sample from a device and return basic signal metrics."""
        rate = find_supported_sample_rate(
            device=device,
            channels=self.channels,
            preferred=self.sample_rate,
        )
        audio = sd.rec(
            int(rate * 1.5),
            samplerate=rate,
            channels=self.channels,
            dtype="float32",
            device=device,
            blocking=True,
        )
        audio = np.asarray(audio, dtype=np.float32)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        return {"success": True, "rate": rate, "peak": peak, "rms": rms}

    @property
    def is_recording(self) -> bool:
        return self.recorder is not None and self.recorder.is_recording

    def transcribing(self) -> bool:
        return self._transcription_future is not None and not self._transcription_future.done()

    def start(self):
        if self.recorder is None:
            self._emit("voice.error", "Микрофон недоступен. Проверь устройство в настройках голоса.")
            return
        if self.is_recording or self.transcribing():
            return
        try:
            self.recorder.start()
            self._silence_stop.clear()
            self._start_silence_monitor()
            self._emit("voice.listening_changed", True)
        except Exception as exc:
            self._emit("voice.error", self._friendly_microphone_error(exc))

    def stop(self):
        self._silence_stop.set()
        if self.recorder is None or not self.recorder.is_recording:
            return
        try:
            audio = self.recorder.stop()
            self._emit("voice.listening_changed", False)
        except Exception as exc:
            logger.exception("voice_recording_stop_failed")
            self._emit("voice.listening_changed", False)
            self._emit("voice.error", f"Не удалось остановить запись: {exc}")
            return

        if len(audio) < int(self.recording_sample_rate * self.min_duration):
            return
        self._transcribe(audio)

    def _start_silence_monitor(self):
        if self._silence_thread and self._silence_thread.is_alive():
            return

        def monitor():
            while not self._silence_stop.wait(0.1):
                recorder = self.recorder
                if recorder is None or not recorder.is_recording:
                    return
                if recorder.has_voice and recorder.silence_duration >= self.silence_duration:
                    logger.info("voice_recording_auto_stopped silence_duration=%.2fs", recorder.silence_duration)
                    self.stop()
                    return

        self._silence_thread = threading.Thread(
            target=monitor,
            name="jarvis-voice-silence",
            daemon=True,
        )
        self._silence_thread.start()

    def _transcribe(self, audio):
        if self.recognizer is None:
            self._emit("voice.error", "Распознаватель речи не инициализирован.")
            return

        self._emit("voice.transcribing_changed", True)
        future = self.tasks.submit(
            self.recognizer.transcribe,
            audio,
            self.recording_sample_rate,
        )
        self._transcription_future = future
        future.add_done_callback(self._transcription_done)

    def _transcription_done(self, future):
        self._transcription_future = None
        self._emit("voice.transcribing_changed", False)
        try:
            raw_text = str(future.result()).strip()
        except Exception as exc:
            logger.exception("voice_transcription_failed")
            self._emit("voice.error", f"Не удалось распознать речь: {exc}")
            return

        if self.recognizer is not None and self.recognizer.last_stats is not None:
            self._emit("voice.whisper_stats", self.recognizer.last_stats)

        if not raw_text:
            return

        normalized_text = normalize_voice_command(raw_text)
        logger.info("voice_command_normalized raw=%r normalized=%r", raw_text, normalized_text)
        if normalized_text:
            self._emit("voice.transcript_ready", normalized_text)

    @staticmethod
    def _friendly_microphone_error(exc: Exception) -> str:
        return (
            "Не удалось подключиться к выбранному микрофону. Проверь, что он подключён "
            f"и JARVIS имеет доступ к нему. Детали: {exc}"
        )

    def close(self):
        self._silence_stop.set()
        if self.recorder is not None and self.recorder.is_recording:
            try:
                self.recorder.stop()
            except Exception:
                logger.exception("voice_close_recording_stop_failed")
            self._emit("voice.listening_changed", False)

        if self.recognizer is not None:
            unload_stats = self.recognizer.close()
            if unload_stats is not None:
                self._emit("voice.whisper_stats", unload_stats)
            self.recognizer = None
