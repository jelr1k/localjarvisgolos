from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from voice import devices


def test_find_input_device_by_name_returns_preferred_device():
    raw = [
        {"name": "USB MIC", "max_input_channels": 1, "hostapi": 1},
        {"name": "Other", "max_input_channels": 1, "hostapi": 0},
    ]
    hostapis = [{"name": "MME"}, {"name": "Windows WASAPI"}]

    with patch("voice.devices.sd.query_devices", return_value=raw), patch("voice.devices.sd.query_hostapis", return_value=hostapis):
        result = devices.find_input_device_by_name(" usb   mic ")

    assert result is not None
    assert result["index"] == 0
    assert result["hostapi_name"] == "Windows WASAPI"


def test_find_input_device_by_name_handles_missing_device_and_api_failure():
    with patch("voice.devices.sd.query_devices", return_value=[]), patch("voice.devices.sd.query_hostapis", return_value=[]):
        assert devices.find_input_device_by_name("missing") is None
    assert devices.find_input_device_by_name(None) is None

    with patch("voice.devices.sd.query_devices", side_effect=RuntimeError("boom")):
        assert devices.find_input_device_by_name("mic") is None


def test_resolve_shared_input_device_prefers_matching_wasapi_duplicate():
    raw = [
        {"name": "USB Mic", "max_input_channels": 1, "hostapi": 0},
        {"name": "USB Mic", "max_input_channels": 1, "hostapi": 1},
    ]
    hostapis = [{"name": "Windows WASAPI"}, {"name": "MME"}]

    with patch("voice.devices.sd.query_devices", return_value=raw), patch("voice.devices.sd.query_hostapis", return_value=hostapis):
        assert devices.resolve_shared_input_device(1) == 0


def test_resolve_shared_input_device_keeps_wasapi_and_invalid_values():
    raw = [{"name": "USB Mic", "max_input_channels": 1, "hostapi": 0}]
    hostapis = [{"name": "Windows WASAPI"}]

    with patch("voice.devices.sd.query_devices", return_value=raw), patch("voice.devices.sd.query_hostapis", return_value=hostapis):
        assert devices.resolve_shared_input_device(0) == 0
        assert devices.resolve_shared_input_device(9) == 9
        assert devices.resolve_shared_input_device(None) is None


def test_resolve_shared_input_device_returns_original_on_api_error():
    with patch("voice.devices.sd.query_devices", side_effect=RuntimeError("boom")):
        assert devices.resolve_shared_input_device(4) == 4


def test_get_shared_input_extra_settings_returns_none_for_non_wasapi():
    with patch("voice.devices.resolve_shared_input_device", return_value=2), patch("voice.devices.sd.query_devices", return_value={"hostapi": 0}), patch("voice.devices.sd.query_hostapis", return_value=[{"name": "MME"}]):
        assert devices.get_shared_input_extra_settings(2) is None


def test_get_shared_input_extra_settings_requests_shared_wasapi():
    wasapi = object()
    with patch("voice.devices.resolve_shared_input_device", return_value=2), patch("voice.devices.sd.query_devices", return_value={"hostapi": 0}), patch("voice.devices.sd.query_hostapis", return_value=[{"name": "Windows WASAPI"}]), patch("voice.devices.sd.WasapiSettings", return_value=wasapi) as factory:
        result = devices.get_shared_input_extra_settings(2)

    assert result is wasapi
    factory.assert_called_once_with(exclusive=False)


def test_get_shared_input_extra_settings_handles_errors():
    with patch("voice.devices.resolve_shared_input_device", side_effect=RuntimeError("boom")):
        assert devices.get_shared_input_extra_settings(2) is None


def test_find_supported_sample_rate_uses_preferred_then_fallback():
    checked = []

    def check(**kwargs):
        checked.append(kwargs["samplerate"])
        if kwargs["samplerate"] != 48000:
            raise ValueError("unsupported")

    with patch("voice.devices.sd.check_input_settings", side_effect=check):
        assert devices.find_supported_sample_rate(preferred=16000) == 48000

    assert checked[:2] == [16000, 48000]


def test_find_supported_sample_rate_raises_when_no_candidate_works():
    with patch("voice.devices.sd.check_input_settings", side_effect=ValueError("nope")):
        with pytest.raises(ValueError, match="не принимает"):
            devices.find_supported_sample_rate(preferred=16000)
