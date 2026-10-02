from __future__ import annotations

import pytest

from core.config_manager import ConfigManager
from security.permissions import PermissionManager
from security.sandbox import SandboxError, is_inside_sandbox, resolve_inside_sandbox, sandbox_root
from security.validator import validate_non_empty, validate_tool_name, validate_url


def test_sandbox_accepts_workspace_path():
    path = resolve_inside_sandbox("tests/example.txt")
    assert path.is_relative_to(sandbox_root())


def test_sandbox_rejects_path_outside_workspace():
    with pytest.raises(SandboxError):
        resolve_inside_sandbox("..")


def test_sandbox_boolean_helper_matches_resolution():
    assert is_inside_sandbox("folder/file.txt")
    assert not is_inside_sandbox("C:/Windows/system32")


def test_sandbox_rejects_empty_path():
    with pytest.raises(SandboxError):
        resolve_inside_sandbox("")


def test_url_validator_accepts_http_and_https():
    assert validate_url("https://example.com") == "https://example.com"
    assert validate_url("http://localhost:11434") == "http://localhost:11434"


@pytest.mark.parametrize("value", ["example.com", "ftp://example.com", ""])
def test_url_validator_rejects_invalid_urls(value):
    with pytest.raises(ValueError):
        validate_url(value)


def test_non_empty_validator_normalizes_text():
    assert validate_non_empty("  Jarvis  ", "name") == "Jarvis"


def test_tool_name_validator_rejects_path_separators():
    with pytest.raises(ValueError):
        validate_tool_name("../tool")


def test_permission_manager_reads_and_updates_config(tmp_path):
    config = ConfigManager(tmp_path / "settings.json")
    permissions = PermissionManager(config)

    config.data["tools"]["example_tool"] = False
    assert not permissions.is_enabled("example_tool")

    permissions.update("example_tool", True)
    assert permissions.is_enabled("example_tool")
