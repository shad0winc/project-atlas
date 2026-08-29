"""Directory-mode contract tests for Atlas user profiles."""

from __future__ import annotations

import os
from pathlib import Path

from atlas.user_profiles import UserProfileStore, default_store


def _mode(path: Path) -> int:
    return path.stat().st_mode & 0o7777


def test_generic_store_keeps_private_profile_directory_mode(
    tmp_path: Path,
) -> None:
    store = UserProfileStore(tmp_path / "users")

    profile = store.create_user("generic-user")

    assert _mode(
        store.profiles_directory / profile["user_id"]
    ) == 0o2750


def test_default_store_creates_writer_compatible_profile_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("ATLAS_USERS_DIR", str(users_root))
    store = default_store()

    profile = store.create_user("canonical-user")

    assert _mode(
        store.profiles_directory / profile["user_id"]
    ) == 0o2770

def test_default_store_profile_mode_survives_restrictive_umask(
    tmp_path: Path,
    monkeypatch,
) -> None:
    users_root = tmp_path / "users"
    monkeypatch.setenv("ATLAS_USERS_DIR", str(users_root))
    store = default_store()

    previous_umask = os.umask(0o077)
    try:
        profile = store.create_user("umask-user")
    finally:
        os.umask(previous_umask)

    assert _mode(
        store.profiles_directory / profile["user_id"]
    ) == 0o2770
