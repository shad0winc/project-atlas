from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_api.authorization.catalog import (
    BUILT_IN_ROLES,
    SPORTS_ADMIN_ROLE,
)
from atlas_api.routes.v1 import (
    admin_sports_providers,
)
from atlas_api.services.sports import (
    SportsWriterBackedAPIService,
    SportsWriterTransportError,
)


TEST_USER_ID = "sports-admin-test"


class _FakeAdminUser:
    user_id = TEST_USER_ID


class FakeSportsWriter:
    def get_source_registry(self):
        return {
            "providers": [
                {
                    "provider_id": "provider-a",
                    "display_name": "Provider A",
                    "account_count": 2,
                    "enabled_account_count": 2,
                    "configured_max_connections": 6,
                    "enabled_max_connections": 6,
                    "source_ids": [
                        "provider-a-primary",
                        "provider-a-multi",
                    ],
                }
            ],
            "sources": [
                {
                    "source_id": "provider-a-primary",
                    "display_name": (
                        "Provider A / Primary"
                    ),
                    "provider_id": "provider-a",
                    "provider_display_name": (
                        "Provider A"
                    ),
                    "account_display_name": "Primary",
                    "kind": "licensed_subscription",
                    "trust_class": "licensed",
                    "enabled": True,
                    "priority": 100,
                    "max_connections": 1,
                    "backend_reference": (
                        "dispatcharr:m3u:2"
                    ),
                    "purchased_at": None,
                    "expires_at": (
                        "2027-09-04T20:58:41+00:00"
                    ),
                    "renewal_url": None,
                    "renewal_notice_days": [
                        30,
                        14,
                        7,
                        3,
                        1,
                    ],
                },
                {
                    "source_id": "provider-a-multi",
                    "display_name": (
                        "Provider A / Multi"
                    ),
                    "provider_id": "provider-a",
                    "provider_display_name": (
                        "Provider A"
                    ),
                    "account_display_name": (
                        "Multi-stream"
                    ),
                    "kind": "licensed_subscription",
                    "trust_class": "licensed",
                    "enabled": True,
                    "priority": 200,
                    "max_connections": 5,
                    "backend_reference": (
                        "dispatcharr:m3u:7"
                    ),
                    "purchased_at": None,
                    "expires_at": None,
                    "renewal_url": None,
                    "renewal_notice_days": [
                        30,
                        14,
                        7,
                        3,
                        1,
                    ],
                },
            ],
        }


def _client(
    writer: object,
    audit_writer: object | None = None,
) -> TestClient:
    app = FastAPI()

    app.include_router(
        admin_sports_providers.router
    )

    app.dependency_overrides[
        admin_sports_providers.
        require_sports_providers_manage
    ] = lambda: _FakeAdminUser()

    app.dependency_overrides[
        admin_sports_providers.
        get_admin_sports_service
    ] = lambda: writer

    if audit_writer is not None:
        app.dependency_overrides[
            admin_sports_providers.
            get_security_audit_writer
        ] = lambda: audit_writer

    return TestClient(app)


def test_sports_admin_has_provider_manage_permission() -> None:
    role = BUILT_IN_ROLES[
        SPORTS_ADMIN_ROLE
    ]

    assert (
        "sports.providers.manage"
        in role.permissions
    )


def test_provider_read_api_groups_accounts_and_hides_backend_reference() -> None:
    response = _client(
        FakeSportsWriter()
    ).get(
        "/admin/sports/providers"
    )

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "providers": [
            {
                "provider_id": "provider-a",
                "display_name": "Provider A",
                "account_count": 2,
                "enabled_account_count": 2,
                "configured_max_connections": 6,
                "enabled_max_connections": 6,
                "accounts": [
                    {
                        "source_id": (
                            "provider-a-primary"
                        ),
                        "display_name": (
                            "Provider A / Primary"
                        ),
                        "account_display_name": (
                            "Primary"
                        ),
                        "enabled": True,
                        "kind": (
                            "licensed_subscription"
                        ),
                        "trust_class": "licensed",
                        "priority": 100,
                        "max_connections": 1,
                        "expires_at": (
                            "2027-09-04T20:58:41+00:00"
                        ),
                        "backend_configured": True,
                    },
                    {
                        "source_id": (
                            "provider-a-multi"
                        ),
                        "display_name": (
                            "Provider A / Multi"
                        ),
                        "account_display_name": (
                            "Multi-stream"
                        ),
                        "enabled": True,
                        "kind": (
                            "licensed_subscription"
                        ),
                        "trust_class": "licensed",
                        "priority": 200,
                        "max_connections": 5,
                        "expires_at": None,
                        "backend_configured": True,
                    },
                ],
            }
        ]
    }

    serialized = response.text.lower()

    assert "backend_reference" not in serialized
    assert "password" not in serialized
    assert "username" not in serialized
    assert "server_url" not in serialized
    assert "api_key" not in serialized
    assert "token" not in serialized


def test_provider_read_api_maps_writer_failure_to_503() -> None:
    class FailedWriter:
        def get_source_registry(self):
            raise SportsWriterTransportError(
                "writer unavailable"
            )

    response = _client(
        FailedWriter()
    ).get(
        "/admin/sports/providers"
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "Sports provider administration "
            "is unavailable."
        )
    }


def test_writer_adapter_rejects_credential_fields(
    monkeypatch,
) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://writer.test",
        token="test-token",
    )

    monkeypatch.setattr(
        service,
        "_request",
        lambda *_args, **_kwargs: {
            "providers": [],
            "sources": [
                {
                    "source_id": "unsafe",
                    "password": "must-not-pass",
                }
            ],
        },
    )

    try:
        service.get_source_registry()
    except SportsWriterTransportError:
        pass
    else:
        raise AssertionError(
            "credential-bearing payload "
            "must be rejected"
        )


class MutableFakeSportsWriter(
    FakeSportsWriter
):
    def __init__(self) -> None:
        self.provider_updates = []
        self.source_updates = []

    def update_provider_display_name(
        self,
        *,
        provider_id: str,
        display_name: str,
    ):
        self.provider_updates.append(
            (
                provider_id,
                display_name,
            )
        )

        registry = self.get_source_registry()

        registry["providers"][0][
            "display_name"
        ] = display_name

        for source in registry["sources"]:
            source[
                "provider_display_name"
            ] = display_name

        return registry

    def update_source_metadata(
        self,
        *,
        source_id: str,
        fields,
    ):
        self.source_updates.append(
            (
                source_id,
                dict(fields),
            )
        )

        registry = self.get_source_registry()

        for source in registry["sources"]:
            if (
                source["source_id"]
                == source_id
            ):
                source.update(fields)

        # Keep aggregate values consistent with
        # the account state returned by this fake.
        provider = registry["providers"][0]
        sources = registry["sources"]

        provider[
            "enabled_account_count"
        ] = sum(
            1
            for source in sources
            if source["enabled"]
        )

        provider[
            "configured_max_connections"
        ] = sum(
            source["max_connections"]
            for source in sources
        )

        provider[
            "enabled_max_connections"
        ] = sum(
            source["max_connections"]
            for source in sources
            if source["enabled"]
        )

        return registry


def test_provider_can_be_renamed_without_changing_id() -> None:
    writer = MutableFakeSportsWriter()

    response = _client(writer).patch(
        "/admin/sports/providers/provider-a",
        json={
            "display_name": (
                "Friendly Provider"
            ),
        },
    )

    assert response.status_code == 200

    assert writer.provider_updates == [
        (
            "provider-a",
            "Friendly Provider",
        )
    ]

    provider = response.json()[
        "providers"
    ][0]

    assert (
        provider["provider_id"]
        == "provider-a"
    )
    assert (
        provider["display_name"]
        == "Friendly Provider"
    )


def test_account_safe_metadata_can_be_updated() -> None:
    writer = MutableFakeSportsWriter()

    response = _client(writer).patch(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary"
        ),
        json={
            "account_display_name": (
                "Main License"
            ),
            "enabled": False,
            "max_connections": 3,
        },
    )

    assert response.status_code == 200

    assert writer.source_updates == [
        (
            "provider-a-primary",
            {
                "account_display_name": (
                    "Main License"
                ),
                "enabled": False,
                "max_connections": 3,
            },
        )
    ]


def test_account_update_is_provider_scoped() -> None:
    writer = MutableFakeSportsWriter()

    response = _client(writer).patch(
        (
            "/admin/sports/providers/"
            "wrong-provider/accounts/"
            "provider-a-primary"
        ),
        json={
            "enabled": False,
        },
    )

    assert response.status_code == 404
    assert writer.source_updates == []


def test_account_update_rejects_empty_change() -> None:
    writer = MutableFakeSportsWriter()

    response = _client(writer).patch(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary"
        ),
        json={},
    )

    assert response.status_code == 422
    assert writer.source_updates == []


def test_account_update_rejects_nonpositive_capacity() -> None:
    writer = MutableFakeSportsWriter()

    response = _client(writer).patch(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary"
        ),
        json={
            "max_connections": 0,
        },
    )

    assert response.status_code == 422
    assert writer.source_updates == []


def test_account_metadata_endpoint_rejects_stable_identity_fields() -> None:
    writer = MutableFakeSportsWriter()

    for forbidden in (
        "source_id",
        "provider_id",
        "backend_reference",
        "username",
        "password",
        "server_url",
    ):
        response = _client(writer).patch(
            (
                "/admin/sports/providers/"
                "provider-a/accounts/"
                "provider-a-primary"
            ),
            json={
                forbidden: "forbidden",
            },
        )

        assert response.status_code == 422

    assert writer.source_updates == []


def test_provider_metadata_endpoint_rejects_stable_identity_and_credentials() -> None:
    writer = MutableFakeSportsWriter()

    for forbidden in (
        "provider_id",
        "backend_reference",
        "username",
        "password",
        "server_url",
    ):
        response = _client(writer).patch(
            "/admin/sports/providers/provider-a",
            json={
                "display_name": "Provider A",
                forbidden: "forbidden",
            },
        )

        assert response.status_code == 422

    assert writer.provider_updates == []


def test_writer_service_provider_rename_uses_atomic_provider_route(
    monkeypatch,
) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://writer.test",
        token="test-token",
    )

    calls = []

    payload = (
        FakeSportsWriter()
        .get_source_registry()
    )

    def request(
        method,
        path,
        body=None,
    ):
        calls.append(
            (
                method,
                path,
                body,
            )
        )
        return payload

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    result = (
        service.update_provider_display_name(
            provider_id="provider a",
            display_name="Renamed Provider",
        )
    )

    assert calls == [
        (
            "PATCH",
            (
                "/internal/v1/providers/"
                "provider%20a"
            ),
            {
                "provider_display_name": (
                    "Renamed Provider"
                )
            },
        )
    ]

    assert result["providers"]


def test_writer_service_account_mutation_allows_only_safe_fields(
    monkeypatch,
) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://writer.test",
        token="test-token",
    )

    calls = []

    payload = (
        FakeSportsWriter()
        .get_source_registry()
    )

    def request(
        method,
        path,
        body=None,
    ):
        calls.append(
            (
                method,
                path,
                body,
            )
        )
        return payload

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    service.update_source_metadata(
        source_id="source one",
        fields={
            "account_display_name": "Main",
            "enabled": True,
            "max_connections": 4,
        },
    )

    assert calls == [
        (
            "PATCH",
            (
                "/internal/v1/sources/"
                "source%20one"
            ),
            {
                "account_display_name": "Main",
                "enabled": True,
                "max_connections": 4,
            },
        )
    ]

    for forbidden in (
        "provider_id",
        "source_id",
        "backend_reference",
        "password",
        "username",
        "server_url",
    ):
        try:
            service.update_source_metadata(
                source_id="source-one",
                fields={
                    forbidden: "forbidden",
                },
            )
        except ValueError:
            pass
        else:
            raise AssertionError(
                f"{forbidden} must not be editable"
            )


class ConnectionFakeSportsWriter(
    MutableFakeSportsWriter
):
    def __init__(self) -> None:
        super().__init__()
        self.account_reads = []
        self.connection_tests = []

    def get_dispatcharr_account(
        self,
        *,
        source_id: str,
    ):
        self.account_reads.append(
            source_id
        )

        return {
            "account_id": 2,
            "name": "Provider Account",
            "account_type": "XC",
            "enabled": False,
            "configured_max_connections": 1,
            "credentials_configured": True,
        }

    def test_dispatcharr_connection(
        self,
        *,
        source_id: str,
    ):
        self.connection_tests.append(
            source_id
        )

        return {
            "ok": True,
            "status": "Active",
            "expires_at": "1234567890",
            "provider_max_connections": 1,
            "active_connections": 0,
        }


def test_admin_can_read_secret_safe_connection_configuration() -> None:
    writer = ConnectionFakeSportsWriter()

    response = _client(writer).get(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary/connection"
        )
    )

    assert response.status_code == 200

    assert response.json() == {
        "account_id": 2,
        "name": "Provider Account",
        "account_type": "XC",
        "enabled": False,
        "configured_max_connections": 1,
        "credentials_configured": True,
    }

    serialized = response.text.lower()

    for forbidden in (
        "password",
        "username",
        "server_url",
        "token",
        "api_key",
    ):
        assert forbidden not in serialized


def test_admin_can_run_secret_safe_connection_test() -> None:
    writer = ConnectionFakeSportsWriter()

    response = _client(writer).post(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary/"
            "test-connection"
        )
    )

    assert response.status_code == 200

    assert writer.connection_tests == [
        "provider-a-primary"
    ]

    assert response.json() == {
        "ok": True,
        "status": "Active",
        "expires_at": "1234567890",
        "provider_max_connections": 1,
        "active_connections": 0,
    }


def test_connection_routes_are_provider_scoped() -> None:
    writer = ConnectionFakeSportsWriter()

    read_response = _client(
        writer
    ).get(
        (
            "/admin/sports/providers/"
            "wrong/accounts/"
            "provider-a-primary/connection"
        )
    )

    test_response = _client(
        writer
    ).post(
        (
            "/admin/sports/providers/"
            "wrong/accounts/"
            "provider-a-primary/"
            "test-connection"
        )
    )

    assert read_response.status_code == 404
    assert test_response.status_code == 404
    assert writer.account_reads == []
    assert writer.connection_tests == []


def test_connection_response_models_exclude_credentials() -> None:
    from atlas_api.routes.v1.admin_sports_providers import (
        AdminSportsConnectionTestResponse,
        AdminSportsDispatcharrAccountResponse,
    )

    fields = (
        set(
            AdminSportsConnectionTestResponse
            .model_fields
        )
        | set(
            AdminSportsDispatcharrAccountResponse
            .model_fields
        )
    )

    for forbidden in (
        "password",
        "username",
        "server_url",
        "token",
        "api_key",
        "backend_reference",
    ):
        assert forbidden not in fields


def test_writer_dispatcharr_adapters_accept_only_safe_shapes(
    monkeypatch,
) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://writer.test",
        token="test-token",
    )

    calls = []

    def request(
        method,
        path,
        body=None,
    ):
        calls.append(
            (
                method,
                path,
                body,
            )
        )

        if method == "GET":
            return {
                "account": {
                    "account_id": 2,
                    "name": "Provider Account",
                    "account_type": "XC",
                    "enabled": False,
                    "configured_max_connections": 1,
                    "credentials_configured": True,
                }
            }

        return {
            "connection": {
                "ok": True,
                "status": "Active",
                "expires_at": "123",
                "provider_max_connections": 1,
                "active_connections": 0,
            }
        }

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    account = (
        service.get_dispatcharr_account(
            source_id="source one"
        )
    )

    result = (
        service.test_dispatcharr_connection(
            source_id="source one"
        )
    )

    assert account[
        "credentials_configured"
    ] is True
    assert result["ok"] is True

    assert calls == [
        (
            "GET",
            (
                "/internal/v1/sources/"
                "source%20one/"
                "dispatcharr-account"
            ),
            None,
        ),
        (
            "POST",
            (
                "/internal/v1/sources/"
                "source%20one/"
                "test-connection"
            ),
            {},
        ),
    ]


def test_writer_dispatcharr_account_adapter_rejects_secret_fields(
    monkeypatch,
) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://writer.test",
        token="test-token",
    )

    monkeypatch.setattr(
        service,
        "_request",
        lambda *_args, **_kwargs: {
            "account": {
                "account_id": 2,
                "name": "Provider Account",
                "account_type": "XC",
                "enabled": False,
                "configured_max_connections": 1,
                "credentials_configured": True,
                "username": "must-not-pass",
            }
        },
    )

    try:
        service.get_dispatcharr_account(
            source_id="source-one"
        )
    except SportsWriterTransportError:
        pass
    else:
        raise AssertionError(
            "secret-bearing account response "
            "must fail closed"
        )


class CredentialUpdateFakeSportsWriter(
    ConnectionFakeSportsWriter
):
    def __init__(self) -> None:
        super().__init__()
        self.connection_updates = []

    def update_dispatcharr_credentials(
        self,
        *,
        source_id: str,
        server_url=None,
        username=None,
        password=None,
    ):
        self.connection_updates.append(
            {
                "source_id": source_id,
                "server_url": server_url,
                "username": username,
                "password": password,
            }
        )

        return {
            "account_id": 2,
            "name": "Provider Account",
            "account_type": "XC",
            "enabled": False,
            "configured_max_connections": 1,
            "credentials_configured": True,
        }


class FakeSportsSecurityAuditWriter:
    def __init__(self) -> None:
        self.events = []

    def publish(
        self,
        name,
        metadata,
    ):
        self.events.append(
            (
                name,
                metadata,
            )
        )


def test_admin_can_update_allowlisted_provider_connection_fields() -> None:
    writer = CredentialUpdateFakeSportsWriter()
    audit = FakeSportsSecurityAuditWriter()

    client = _client(
        writer,
        audit_writer=audit,
    )

    response = client.patch(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary/credentials"
        ),
        json={
            "server_url": (
                "https://provider.invalid"
            ),
            "username": "replacement-user",
            "password": "replacement-value",
        },
    )

    assert response.status_code == 200

    assert writer.connection_updates == [
        {
            "source_id": (
                "provider-a-primary"
            ),
            "server_url": (
                "https://provider.invalid"
            ),
            "username": (
                "replacement-user"
            ),
            "password": (
                "replacement-value"
            ),
        }
    ]

    assert response.json() == {
        "account_id": 2,
        "name": "Provider Account",
        "account_type": "XC",
        "enabled": False,
        "configured_max_connections": 1,
        "credentials_configured": True,
    }

    assert audit.events == [
        (
            (
                "security.sports."
                "provider_connection_updated"
            ),
            {
                "actor_user_id": (
                    TEST_USER_ID
                ),
                "provider_id": "provider-a",
                "source_id": (
                    "provider-a-primary"
                ),
            },
        )
    ]

    serialized_audit = repr(
        audit.events
    )

    assert (
        "replacement-user"
        not in serialized_audit
    )
    assert (
        "replacement-value"
        not in serialized_audit
    )
    assert (
        "provider.invalid"
        not in serialized_audit
    )


def test_admin_blank_password_is_forwarded_as_retain_current() -> None:
    writer = CredentialUpdateFakeSportsWriter()
    audit = FakeSportsSecurityAuditWriter()

    response = _client(
        writer,
        audit_writer=audit,
    ).patch(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary/credentials"
        ),
        json={
            "password": "",
        },
    )

    assert response.status_code == 200

    assert writer.connection_updates == [
        {
            "source_id": (
                "provider-a-primary"
            ),
            "server_url": None,
            "username": None,
            "password": "",
        }
    ]


def test_admin_connection_update_rejects_extra_fields() -> None:
    writer = CredentialUpdateFakeSportsWriter()
    audit = FakeSportsSecurityAuditWriter()

    response = _client(
        writer,
        audit_writer=audit,
    ).patch(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary/credentials"
        ),
        json={
            "is_active": True,
        },
    )

    assert response.status_code == 422
    assert writer.connection_updates == []
    assert audit.events == []


def test_admin_connection_update_rejects_empty_body() -> None:
    writer = CredentialUpdateFakeSportsWriter()
    audit = FakeSportsSecurityAuditWriter()

    response = _client(
        writer,
        audit_writer=audit,
    ).patch(
        (
            "/admin/sports/providers/"
            "provider-a/accounts/"
            "provider-a-primary/credentials"
        ),
        json={},
    )

    assert response.status_code == 422
    assert writer.connection_updates == []
    assert audit.events == []


def test_admin_connection_update_wrong_provider_is_not_mutated_or_audited() -> None:
    writer = CredentialUpdateFakeSportsWriter()
    audit = FakeSportsSecurityAuditWriter()

    response = _client(
        writer,
        audit_writer=audit,
    ).patch(
        (
            "/admin/sports/providers/"
            "wrong/accounts/"
            "provider-a-primary/credentials"
        ),
        json={
            "username": "new-user",
        },
    )

    assert response.status_code == 404
    assert writer.connection_updates == []
    assert audit.events == []


def test_writer_credential_adapter_uses_only_allowlisted_private_body(
    monkeypatch,
) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://writer.test",
        token="test-token",
    )

    captured = {}

    def request(
        method,
        path,
        body=None,
    ):
        captured.update(
            {
                "method": method,
                "path": path,
                "body": body,
            }
        )

        return {
            "account": {
                "account_id": 2,
                "name": "Provider Account",
                "account_type": "XC",
                "enabled": False,
                "configured_max_connections": 1,
                "credentials_configured": True,
            }
        }

    monkeypatch.setattr(
        service,
        "_request",
        request,
    )

    result = (
        service.update_dispatcharr_credentials(
            source_id="source one",
            server_url=(
                "https://provider.invalid"
            ),
            username="replacement-user",
            password="",
        )
    )

    assert result[
        "credentials_configured"
    ] is True

    assert captured == {
        "method": "PATCH",
        "path": (
            "/internal/v1/sources/"
            "source%20one/credentials"
        ),
        "body": {
            "server_url": (
                "https://provider.invalid"
            ),
            "username": (
                "replacement-user"
            ),
            "password": "",
        },
    }


def test_resource_pool_reports_enabled_capacity_and_active_leases(
    tmp_path,
) -> None:
    from atlas.sports_resource_pool import SportsResourcePool

    resource_pool = SportsResourcePool(
        tmp_path / "sports-resource-pool.json"
    )

    resource_pool.acquire(
        user_id="usr-one",
        target_id="game-one",
        candidate_source_ids=(
            "provider-a-multi",
        ),
        capacities={
            "provider-a-primary": 1,
            "provider-a-multi": 5,
        },
    )

    resource_pool.acquire(
        user_id="usr-two",
        target_id="game-two",
        candidate_source_ids=(
            "provider-a-multi",
        ),
        capacities={
            "provider-a-primary": 1,
            "provider-a-multi": 5,
        },
    )

    app = FastAPI()
    app.include_router(
        admin_sports_providers.router
    )

    app.dependency_overrides[
        admin_sports_providers.
        require_sports_providers_manage
    ] = lambda: _FakeAdminUser()

    app.dependency_overrides[
        admin_sports_providers.
        get_admin_sports_service
    ] = lambda: FakeSportsWriter()

    app.dependency_overrides[
        admin_sports_providers.
        get_sports_resource_pool
    ] = lambda: resource_pool

    response = TestClient(app).get(
        "/admin/sports/providers/resource-pool"
    )

    assert response.status_code == 200

    assert response.json() == {
        "total_capacity": 6,
        "active": 2,
        "available": 4,
        "accounts": [
            {
                "source_id": "provider-a-multi",
                "enabled": True,
                "capacity": 5,
                "active": 2,
                "available": 3,
            },
            {
                "source_id": "provider-a-primary",
                "enabled": True,
                "capacity": 1,
                "active": 0,
                "available": 1,
            },
        ],
    }

    serialized = response.text.lower()

    assert "backend_reference" not in serialized
    assert "password" not in serialized
    assert "username" not in serialized
    assert "server_url" not in serialized
    assert "api_key" not in serialized
    assert "token" not in serialized


def test_disabled_provider_account_contributes_zero_pool_capacity(
    tmp_path,
) -> None:
    from atlas.sports_resource_pool import SportsResourcePool

    class PartiallyDisabledWriter(
        FakeSportsWriter
    ):
        def get_source_registry(self):
            registry = super().get_source_registry()

            registry["sources"][0][
                "enabled"
            ] = False

            return registry

    resource_pool = SportsResourcePool(
        tmp_path / "sports-resource-pool.json"
    )

    app = FastAPI()
    app.include_router(
        admin_sports_providers.router
    )

    app.dependency_overrides[
        admin_sports_providers.
        require_sports_providers_manage
    ] = lambda: _FakeAdminUser()

    app.dependency_overrides[
        admin_sports_providers.
        get_admin_sports_service
    ] = lambda: PartiallyDisabledWriter()

    app.dependency_overrides[
        admin_sports_providers.
        get_sports_resource_pool
    ] = lambda: resource_pool

    response = TestClient(app).get(
        "/admin/sports/providers/resource-pool"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total_capacity"] == 5
    assert body["active"] == 0
    assert body["available"] == 5

    accounts = {
        item["source_id"]: item
        for item in body["accounts"]
    }

    assert accounts[
        "provider-a-primary"
    ] == {
        "source_id": "provider-a-primary",
        "enabled": False,
        "capacity": 0,
        "active": 0,
        "available": 0,
    }

    assert accounts[
        "provider-a-multi"
    ]["capacity"] == 5
