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

_SAMPLE_RATE_CANDIDATES = (16000, 48000, 44100, 32000, 24000, 22050, 8000)


def _normalize_name(name: str) -> str:
    """Normalize a PortAudio device name for duplicate detection and matching."""
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


def list_input_devices(
    devices: list[dict[str, Any]],
    hostapis: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
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
        key = _normalize_name(name) or f"device-{index}"

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


def find_input_device_by_name(name: str | None) -> dict[str, Any] | None:
    """Resolve a previously selected microphone to its current PortAudio index."""
    if not name:
        return None

    try:
        devices = list(sd.query_devices())
        hostapis = list(sd.query_hostapis())
        normalized = _normalize_name(name)
        for device in list_input_devices(devices, hostapis):
            if _normalize_name(str(device.get("name", ""))) == normalized:
                return device
    except Exception:
        return None
    return None


def resolve_shared_input_device(device=None):
    """Resolve an input device to its Windows WASAPI shared-mode duplicate when possible."""
    if device is None:
        return None

    try:
        devices = list(sd.query_devices())
        hostapis = list(sd.query_hostapis())
        numeric_device = int(device)
        if numeric_device < 0 or numeric_device >= len(devices):
            return device

        current = dict(devices[numeric_device])
        current_hostapi = _host_api_name(current, hostapis)
        if current_hostapi == "Windows WASAPI":
            return numeric_device

        current_name = _normalize_name(str(current.get("name", "")))
        if not current_name:
            return device

        for index, candidate in enumerate(devices):
            try:
                if int(candidate.get("max_input_channels", 0)) <= 0:
                    continue
            except (TypeError, ValueError):
                continue
            if _normalize_name(str(candidate.get("name", ""))) != current_name:
                continue
            if _host_api_name(candidate, hostapis) == "Windows WASAPI":
                return index

        return device
    except Exception:
        return device


def get_shared_input_extra_settings(device=None):
    """Return Windows WASAPI shared-mode settings for an input stream."""
    try:
        resolved_device = resolve_shared_input_device(device)
        info = sd.query_devices(resolved_device)
        hostapis = list(sd.query_hostapis())
        hostapi_index = int(info.get("hostapi", -1))
        hostapi_name = (
            str(hostapis[hostapi_index].get("name", ""))
            if 0 <= hostapi_index < len(hostapis)
            else ""
        )
    except Exception:
        return None

    if hostapi_name != "Windows WASAPI":
        return None

    return sd.WasapiSettings(exclusive=False)


def find_supported_sample_rate(device=None, channels: int = 1, preferred: int = 16000) -> int:
    """Return a sample rate accepted by the selected input device."""
    candidates = [int(preferred)] + [
        rate for rate in _SAMPLE_RATE_CANDIDATES if rate != int(preferred)
    ]
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
