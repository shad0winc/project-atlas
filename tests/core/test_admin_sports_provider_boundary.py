from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

ROUTE = (
    ROOT
    / "apps"
    / "api"
    / "atlas_api"
    / "routes"
    / "v1"
    / "admin_sports_providers.py"
)

SERVICE = (
    ROOT
    / "apps"
    / "api"
    / "atlas_api"
    / "services"
    / "sports.py"
)


def test_admin_provider_route_uses_dedicated_permission() -> None:
    text = ROUTE.read_text(
        encoding="utf-8"
    )

    assert (
        '"sports.providers.manage"'
        in text
    )


def test_admin_provider_response_does_not_expose_backend_reference() -> None:
    text = ROUTE.read_text(
        encoding="utf-8"
    )

    response_models = text[
        text.index(
            "class AdminSportsAccountResponse"
        ):
        text.index(
            "def get_admin_sports_service"
        )
    ]

    assert "backend_reference" not in response_models
    assert "backend_configured" in response_models


def test_service_has_defense_in_depth_secret_filter() -> None:
    text = SERVICE.read_text(
        encoding="utf-8"
    )

    assert "def get_source_registry(" in text

    for term in (
        '"password"',
        '"username"',
        '"server_url"',
        '"token"',
        '"api_key"',
        '"secret"',
    ):
        assert term in text


def test_admin_account_mutation_contract_excludes_identity_and_credentials() -> None:
    text = ROUTE.read_text(
        encoding="utf-8"
    )

    model = text[
        text.index(
            "class AdminSportsAccountUpdateRequest"
        ):
        text.index(
            "def _normalized_label"
        )
    ].lower()

    assert "account_display_name" in model
    assert "enabled" in model
    assert "max_connections" in model

    for forbidden in (
        "provider_id",
        "source_id",
        "backend_reference",
        "password",
        "username",
        "server_url",
        "token",
        "api_key",
    ):
        assert forbidden not in model


def test_private_writer_has_atomic_provider_rename_and_immutable_provider_id() -> None:
    writer = (
        ROOT
        / "modules"
        / "sports"
        / "src"
        / "private_api.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        '"/internal/v1/providers/"'
        in writer
    )

    assert (
        "provider_id cannot "
        in writer
    )

    assert (
        "store.write(updated)"
        in writer
    )


def test_connection_models_are_credential_safe() -> None:
    text = ROUTE.read_text(
        encoding="utf-8"
    )

    start = text.index(
        "class AdminSportsDispatcharrAccountResponse"
    )

    end = text.index(
        "def _require_provider_account"
    )

    models = text[
        start:end
    ].lower()

    assert "credentials_configured" in models

    for forbidden in (
        "password",
        "username",
        "server_url",
        "token",
        "api_key",
        "backend_reference",
    ):
        assert forbidden not in models


def test_provider_admin_has_read_test_and_narrow_credential_write_routes() -> None:
    text = ROUTE.read_text(
        encoding="utf-8"
    )

    assert (
        '"/{provider_id}/accounts/{source_id}/connection"'
        in text
    )

    assert (
        '"/{provider_id}/accounts/{source_id}/test-connection"'
        in text
    )

    assert (
        '"/{provider_id}/accounts/{source_id}/credentials"'
        in text
    )

    # Public route delegates through the Atlas Sports
    # service boundary; it must not invoke Dispatcharr
    # directly.
    assert "DispatcharrAdminClient" not in text
    assert "update_credentials(" not in text


def test_provider_connection_update_is_narrow_and_metadata_only_audited() -> None:
    text = ROUTE.read_text(
        encoding="utf-8"
    )

    assert (
        '"/{provider_id}/accounts/{source_id}/credentials"'
        in text
    )

    assert (
        '"security.sports.provider_connection_updated"'
        in text
    )

    audit_start = text.index(
        'audit_writer.publish(\n'
        '        "security.sports.provider_connection_updated"'
    )

    audit_end = text.index(
        "\n    )",
        audit_start,
    )

    audit_block = text[
        audit_start:audit_end
    ].lower()

    assert "actor_user_id" in audit_block
    assert "provider_id" in audit_block
    assert "source_id" in audit_block

    for forbidden in (
        "server_url",
        "username",
        "password",
        "backend_reference",
        "request.",
        "submitted",
    ):
        assert forbidden not in audit_block
