from voice.devices import list_input_devices


def test_duplicate_input_devices_are_collapsed_by_name():
    devices = [
        {"name": "USB Microphone", "max_input_channels": 1, "hostapi": 2},
        {"name": "USB Microphone", "max_input_channels": 1, "hostapi": 0},
        {"name": "Speakers", "max_input_channels": 0, "hostapi": 0},
        {"name": "Laptop Mic", "max_input_channels": 2, "hostapi": 3},
    ]
    hostapis = [
        {"name": "Windows WASAPI"},
        {"name": "WDM-KS"},
        {"name": "DirectSound"},
        {"name": "MME"},
    ]

    result = list_input_devices(devices, hostapis)

    assert [item["name"] for item in result] == ["Laptop Mic", "USB Microphone"]
    assert result[1]["index"] == 1
    assert result[1]["hostapi_name"] == "Windows WASAPI"


def test_duplicate_detection_ignores_case_and_extra_spaces():
    devices = [
        {"name": "  Headset  Microphone ", "max_input_channels": 1, "hostapi": 0},
        {"name": "HEADSET MICROPHONE", "max_input_channels": 1, "hostapi": 1},
    ]
    hostapis = [
        {"name": "Windows WASAPI"},
        {"name": "MME"},
    ]

    result = list_input_devices(devices, hostapis)

    assert len(result) == 1
    assert result[0]["index"] == 0


def test_non_input_devices_are_excluded():
    devices = [
        {"name": "Output Only", "max_input_channels": 0, "hostapi": 0},
        {"name": "Microphone", "max_input_channels": 1, "hostapi": 0},
    ]
    hostapis = [{"name": "Windows WASAPI"}]

    result = list_input_devices(devices, hostapis)

    assert [item["name"] for item in result] == ["Microphone"]
