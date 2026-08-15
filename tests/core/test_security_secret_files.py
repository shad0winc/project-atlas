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


def test_notifications_verification_uses_operator_environment_for_compose_interpolation() -> None:
    content = source("modules/notifications/scripts/verify.sh")

    operator_env = 'OPERATOR_ENV_FILE="$PROJECT_DIR/.env"'
    env_option = '--env-file "$OPERATOR_ENV_FILE"'
    module_env_option = '--env-file "$MODULE_ENV_FILE"'
    compose_validation = 'check "Module compose valid"'

    assert operator_env in content
    assert env_option in content
    assert module_env_option not in content
    assert compose_validation in content
    assert content.index(operator_env) < content.index(compose_validation)
    assert content.index(compose_validation) < content.index(env_option)


def test_sports_verification_uses_operator_then_module_environment() -> None:
    content = source("modules/sports/scripts/verify.sh")

    operator_env = 'OPERATOR_ENV_FILE="$PROJECT_DIR/.env"'
    module_env = 'MODULE_ENV_FILE="$PROJECT_DIR/modules/sports/.env"'
    operator_option = '--env-file "$OPERATOR_ENV_FILE"'
    module_option = '--env-file "$MODULE_ENV_FILE"'
    compose_validation = 'check "Module compose valid"'

    assert operator_env in content
    assert module_env in content
    assert operator_option in content
    assert module_option in content
    assert compose_validation in content

    assert content.index(operator_env) < content.index(compose_validation)
    assert content.index(module_env) < content.index(compose_validation)

    operator_index = content.index(operator_option)
    module_index = content.index(module_option)

    assert content.index(compose_validation) < operator_index
    assert operator_index < module_index
