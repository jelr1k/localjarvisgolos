from __future__ import annotations

import re
from typing import Any

import sounddevice as sd


_HOST_API_PRIORITY = {
    "Windows WASAPI": 0,
    "WDM-KS": 1,
    "DirectSound": 2,
    "MME": 3,
}

# Prefer Whisper's native 16 kHz when the device supports it. Otherwise use a
# common Windows microphone rate and resample before transcription.
_SAMPLE_RATE_CANDIDATES = (16000, 48000, 44100, 32000, 24000, 22050, 8000)


def _normalize_name(name: str) -> str:
    """Normalize a PortAudio device name for duplicate detection."""
    value = " ".join(str(name).strip().split()).casefold()
    return re.sub(r"[^\w\s]+", "", value, flags=re.UNICODE)


def _host_api_name(device: dict[str, Any], hostapis: list[dict[str, Any]]) -> str:
    try:
        hostapi_index = int(device.get("hostapi", -1))
        if 0 <= hostapi_index < len(hostapis):
            return str(hostapis[hostapi_index].get("name", ""))
    except (TypeError, ValueError):
        pass
    return ""


def list_input_devices(devices: list[dict[str, Any]], hostapis: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return unique input devices, collapsing PortAudio host-API duplicates."""
    hostapis = hostapis or []
    grouped: dict[str, list[dict[str, Any]]] = {}

    for index, device in enumerate(devices):
        try:
            if int(device.get("max_input_channels", 0)) <= 0:
                continue
        except (TypeError, ValueError):
            continue

        name = str(device.get("name", f"Микрофон {index}"))
        key = _normalize_name(name)
        if not key:
            key = f"device-{index}"

        item = dict(device)
        item["index"] = index
        item["hostapi_name"] = _host_api_name(item, hostapis)
        grouped.setdefault(key, []).append(item)

    result: list[dict[str, Any]] = []
    for candidates in grouped.values():
        candidates.sort(
            key=lambda item: (
                _HOST_API_PRIORITY.get(item.get("hostapi_name", ""), 99),
                int(item.get("index", 0)),
            )
        )
        result.append(candidates[0])

    result.sort(key=lambda item: str(item.get("name", "")).casefold())
    return result


def find_supported_sample_rate(device=None, channels: int = 1, preferred: int = 16000) -> int:
    """Return a sample rate accepted by the selected input device.

    ``sounddevice``/PortAudio can expose a microphone that works perfectly but
    rejects the application's preferred 16 kHz format. We probe the device
    before opening a stream and prefer 16 kHz when possible.
    """
    candidates = [int(preferred)] + [rate for rate in _SAMPLE_RATE_CANDIDATES if rate != int(preferred)]
    last_error: Exception | None = None

    for rate in candidates:
        try:
            sd.check_input_settings(
                device=device,
                channels=int(channels),
                dtype="float32",
                samplerate=rate,
            )
            return rate
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise ValueError(
            "Выбранный микрофон не принимает ни одну из поддерживаемых частот "
            f"({', '.join(str(rate) for rate in candidates)} Гц). Последняя ошибка: {last_error}"
        ) from last_error
    return int(preferred)
