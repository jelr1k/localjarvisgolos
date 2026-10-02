from __future__ import annotations

from pathlib import Path

import pytest

from services.update_install_policy import UpdateInstallPolicy


def make_policy(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    return UpdateInstallPolicy(
        app,
        app_data_dir=tmp_path / "AppData" / "Jarvis",
        environment={
            "HF_HUB_CACHE": str(tmp_path / "hf-cache"),
            "OLLAMA_MODELS": str(tmp_path / "ollama-models"),
        },
        home_dir=tmp_path / "home",
    )


def test_policy_protects_user_data_and_local_model_directories(tmp_path):
    policy = make_policy(tmp_path)

    assert policy.is_protected(policy.application_root / "workspace" / "notes.txt")
    assert policy.is_protected(policy.application_root / "logs" / "jarvis.log")
    assert policy.is_protected(policy.application_root / "models" / "model.bin")
    assert policy.is_protected(policy.app_data_dir / "settings.json")


def test_policy_protects_external_model_caches(tmp_path):
    policy = make_policy(tmp_path)

    assert policy.is_protected(tmp_path / "hf-cache" / "models--Systran")
    assert policy.is_protected(tmp_path / "ollama-models" / "blobs")


def test_policy_does_not_protect_normal_application_files(tmp_path):
    policy = make_policy(tmp_path)

    assert not policy.is_protected(policy.application_root / "services" / "update_installer.py")
    assert not policy.is_protected(policy.application_root / "config" / "settings.json")


def test_policy_identifies_protected_archive_members(tmp_path):
    policy = make_policy(tmp_path)

    assert policy.is_protected_archive_path("workspace/notes.txt")
    assert policy.is_protected_archive_path("logs/jarvis.log")
    assert policy.is_protected_archive_path("models/whisper.bin")
    assert not policy.is_protected_archive_path("services/update_installer.py")


def test_policy_ignores_unsafe_archive_paths(tmp_path):
    policy = make_policy(tmp_path)

    assert not policy.is_protected_archive_path("../workspace/notes.txt")
    assert not policy.is_protected_archive_path("/workspace/notes.txt")


def test_policy_prefers_explicit_model_cache_environment_variables(tmp_path):
    policy = make_policy(tmp_path)

    protected = policy.protected_external_paths()
    assert tmp_path / "hf-cache" in protected
    assert tmp_path / "ollama-models" in protected
    assert tmp_path / "home" / ".cache" / "huggingface" / "hub" not in protected
    assert tmp_path / "home" / ".ollama" / "models" not in protected


def test_policy_deduplicates_identical_paths(tmp_path):
    app_data = tmp_path / "same"
    policy = UpdateInstallPolicy(
        tmp_path / "app",
        app_data_dir=app_data,
        environment={
            "HF_HUB_CACHE": str(app_data),
            "OLLAMA_MODELS": str(tmp_path / "ollama"),
        },
        home_dir=tmp_path / "home",
    )

    paths = [item.path for item in policy.protected_paths()]
    assert len(paths) == len(set(paths))
