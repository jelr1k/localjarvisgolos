from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from core.alias_manager import AliasManager
from security.permissions import PermissionManager
from security.sandbox import SandboxError, is_inside_sandbox, resolve_inside_sandbox
from security.validator import validate_non_empty, validate_tool_name, validate_url


def test_validate_non_empty_strips_and_rejects_blank():
    assert validate_non_empty("  hello  ") == "hello"
    with pytest.raises(ValueError, match="Не указано"):
        validate_non_empty("   ", "имя")


@pytest.mark.parametrize("value", ["https://example.com", "http://localhost:11434/api"])
def test_validate_url_accepts_http_and_https(value):
    assert validate_url(value) == value


@pytest.mark.parametrize("value", ["ftp://example.com", "example.com", "javascript:alert(1)", "http://"])
def test_validate_url_rejects_unsafe_or_invalid_urls(value):
    with pytest.raises(ValueError):
        validate_url(value)


@pytest.mark.parametrize("value", ["read_file", "launch_application", "tool.test"])
def test_validate_tool_name_accepts_safe_names(value):
    assert validate_tool_name(value) == value


@pytest.mark.parametrize("value", ["../read_file", "read\\file", "read\nfile", ""])
def test_validate_tool_name_rejects_path_or_control_chars(value):
    with pytest.raises(ValueError):
        validate_tool_name(value)


def test_permission_manager_reads_and_persists_updates():
    config = Mock()
    config.data = {"tools": {"search_files": True}}
    config.get.side_effect = lambda key, default=None: config.data.get(key, default)

    manager = PermissionManager(config)

    assert manager.is_enabled("search_files") is True
    assert manager.is_enabled("delete_file") is False

    manager.update("delete_file", True)

    assert config.data["tools"]["delete_file"] is True
    config.save.assert_called_once()


def test_sandbox_blocks_parent_escape_and_outside_symlink(tmp_path):
    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret", encoding="utf-8")

    with pytest.raises(SandboxError):
        with patch("security.sandbox.WORKSPACE_DIR", root):
            resolve_inside_sandbox("../secret.txt")

    link = root / "link.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")

    with __import__("unittest").mock.patch("security.sandbox.WORKSPACE_DIR", root):
        assert is_inside_sandbox(link, allow_nonexistent=False) is False


def test_alias_manager_uses_normalized_keys_for_action_names(tmp_path):
    manager = AliasManager(tmp_path / "aliases.json")
    manager.set_aliases("actions", "launch", ["Запусти"])
    assert manager.resolve("actions", "запусти")["target"] == "launch"
