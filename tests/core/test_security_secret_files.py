from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def source(relative: str) -> str:
    return (PROJECT_ROOT / relative).read_text(encoding="utf-8")


def test_root_install_creates_and_normalizes_private_operator_environment() -> None:
    content = source("scripts/install.sh")

    assert "if [[ -L .env ]]; then" in content
    assert "install -m 0600 .env.example .env" in content
    assert "if [[ ! -f .env ]]; then" in content
    assert "chmod 0600 .env" in content


def test_module_installers_harden_existing_environment_without_creating_it() -> None:
    for relative in (
        "modules/sports/scripts/install.sh",
        "modules/notifications/scripts/install.sh",
    ):
        content = source(relative)

        assert 'if [[ -L "$MODULE_ENV_FILE" ]]; then' in content
        assert 'if [[ -e "$MODULE_ENV_FILE" ]]; then' in content
        assert 'if [[ ! -f "$MODULE_ENV_FILE" ]]; then' in content
        assert 'chmod 0600 "$MODULE_ENV_FILE"' in content
        assert 'install -m 0600' not in content


def test_module_updates_fail_closed_and_harden_before_compose() -> None:
    for relative in (
        "modules/sports/scripts/update.sh",
        "modules/notifications/scripts/update.sh",
    ):
        content = source(relative)

        guard = 'if [[ ! -f "$MODULE_ENV_FILE" || -L "$MODULE_ENV_FILE" ]]; then'
        chmod = 'chmod 0600 "$MODULE_ENV_FILE"'
        compose = "docker compose"

        assert guard in content
        assert chmod in content
        assert content.index(guard) < content.index(chmod) < content.index(compose)


def test_module_verification_requires_private_non_symlink_environment() -> None:
    for relative in (
        "modules/sports/scripts/verify.sh",
        "modules/notifications/scripts/verify.sh",
    ):
        content = source(relative)

        assert 'check "Module environment present" test -f "$MODULE_ENV_FILE"' in content
        assert (
            'check "Module environment is not symbolic link" test ! -L "$MODULE_ENV_FILE"'
            in content
        )
        assert 'check "Module environment permissions private"' in content
        assert '= "600"' in content
