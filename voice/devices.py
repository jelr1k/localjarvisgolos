from __future__ import annotations

import re
from typing import Any


_HOST_API_PRIORITY = {
    "Windows WASAPI": 0,
    "WDM-KS": 1,
    "DirectSound": 2,
    "MME": 3,
}


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
    """Return unique input devices, collapsing PortAudio host-API duplicates.

    The returned ``index`` is the real sounddevice device index that should be
    passed to InputStream. When the same physical device is exposed by several
    Windows host APIs, the most suitable host API is selected automatically.
    """
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
