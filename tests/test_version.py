from core.version import APP_NAME, APP_VERSION, get_version


def test_application_version_is_centralized():
    assert APP_NAME == "JARVIS"
    assert get_version() == APP_VERSION
    assert len(APP_VERSION.split(".")) == 3
    assert all(part.isdigit() for part in APP_VERSION.split("."))
