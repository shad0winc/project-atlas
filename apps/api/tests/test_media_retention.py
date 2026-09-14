"""Authenticated single-item media-retention route regressions."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas.policies import PolicyDecision
from atlas.retention import (
    RetentionDecision,
    RetentionLifecycle,
    RetentionLifecycleRule,
    RetentionLifecycleState,
)


class _RetentionService:
    def __init__(
        self,
        decision: RetentionDecision | Exception,
    ) -> None:
        self._decision = decision
        self.calls: list[tuple[str, str]] = []

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> RetentionDecision:
        self.calls.append((provider, item_id))

        if isinstance(self._decision, Exception):
            raise self._decision

        return self._decision


def _decision(
    *,
    state: RetentionLifecycleState = RetentionLifecycleState.SCHEDULED,
    rule: RetentionLifecycleRule = RetentionLifecycleRule.UNWATCHED_30D,
    eligible: bool = False,
    basis_at: str | None = "2026-08-15T00:00:00Z",
    delete_at: str | None = "2026-09-14T00:00:00Z",
) -> RetentionDecision:
    return RetentionDecision(
        provider="jellyfin",
        item_id="item-1",
        eligible=eligible,
        policy=PolicyDecision(
            provider="jellyfin",
            item_id="item-1",
            action="ignore",
        ),
        lifecycle=RetentionLifecycle(
            state=state,
            rule=rule,
            basis_at=basis_at,
            delete_at=delete_at,
        ),
    )


def _client(
    service: _RetentionService,
) -> TestClient:
    from atlas_api.auth.models import AuthenticatedUser
    from atlas_api.routes.v1.media_retention import (
        get_media_retention_service,
        require_media_retention_read,
        router,
    )

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    app.dependency_overrides[
        require_media_retention_read
    ] = lambda: AuthenticatedUser(
        user_id="usr_0123456789abcdef0123456789abcdef",
        username="member",
        display_name="Member",
        roles=("Member",),
        provider="jellyfin",
        metadata={},
    )

    app.dependency_overrides[
        get_media_retention_service
    ] = lambda: service

    return TestClient(app)


def test_openapi_registers_single_item_retention_route() -> None:
    service = _RetentionService(_decision())
    client = _client(service)

    schema = client.get("/openapi.json").json()

    assert (
        "/api/v1/media/{provider}/{item_id}/retention"
        in schema["paths"]
    )


def test_retention_read_requires_media_read_permission() -> None:
    from fastapi import HTTPException, status

    from atlas_api.auth.models import AuthenticatedUser
    from atlas_api.routes.v1.media_retention import (
        require_media_retention_read,
        router,
    )

    def forbidden() -> AuthenticatedUser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "No assigned role or direct grant "
                "provides the requested permission."
            ),
        )

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[
        require_media_retention_read
    ] = forbidden

    response = TestClient(app).get(
        "/api/v1/media/jellyfin/item-1/retention"
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": (
            "No assigned role or direct grant "
            "provides the requested permission."
        )
    }


def test_reads_authoritative_retention_decision() -> None:
    service = _RetentionService(_decision())
    client = _client(service)

    response = client.get(
        "/api/v1/media/jellyfin/item-1/retention"
    )

    assert response.status_code == 200
    assert service.calls == [
        ("jellyfin", "item-1"),
    ]

    assert response.json() == {
        "provider": "jellyfin",
        "item_id": "item-1",
        "eligible": False,
        "retained": True,
        "lifecycle": {
            "state": "scheduled",
            "rule": "unwatched_30d",
            "basis_at": "2026-08-15T00:00:00Z",
            "delete_at": "2026-09-14T00:00:00Z",
        },
    }


def test_exposes_protected_lifecycle_without_fake_deadline() -> None:
    service = _RetentionService(
        _decision(
            state=RetentionLifecycleState.PROTECTED,
            rule=RetentionLifecycleRule.POLICY_PROTECTED,
            basis_at=None,
            delete_at=None,
        )
    )
    client = _client(service)

    response = client.get(
        "/api/v1/media/jellyfin/item-1/retention"
    )

    assert response.status_code == 200

    assert response.json()["lifecycle"] == {
        "state": "protected",
        "rule": "policy_protected",
        "basis_at": None,
        "delete_at": None,
    }


def test_exposes_eligible_lifecycle() -> None:
    service = _RetentionService(
        _decision(
            state=RetentionLifecycleState.ELIGIBLE,
            rule=RetentionLifecycleRule.DISLIKED_24H,
            eligible=True,
            basis_at="2026-09-13T00:00:00Z",
            delete_at="2026-09-14T00:00:00Z",
        )
    )
    client = _client(service)

    response = client.get(
        "/api/v1/media/jellyfin/item-1/retention"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["eligible"] is True
    assert payload["retained"] is False
    assert payload["lifecycle"]["state"] == "eligible"
    assert payload["lifecycle"]["rule"] == "disliked_24h"
    assert (
        payload["lifecycle"]["delete_at"]
        == "2026-09-14T00:00:00Z"
    )


def test_exposes_unknown_fail_closed_lifecycle() -> None:
    service = _RetentionService(
        _decision(
            state=RetentionLifecycleState.UNKNOWN,
            rule=RetentionLifecycleRule.UNAVAILABLE,
            basis_at=None,
            delete_at=None,
        )
    )
    client = _client(service)

    response = client.get(
        "/api/v1/media/jellyfin/item-1/retention"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["eligible"] is False
    assert payload["retained"] is True
    assert payload["lifecycle"] == {
        "state": "unknown",
        "rule": "unavailable",
        "basis_at": None,
        "delete_at": None,
    }


def test_route_does_not_recompute_deadline() -> None:
    delete_at = "2037-05-06T07:08:09Z"

    service = _RetentionService(
        _decision(
            basis_at="2026-01-01T00:00:00Z",
            delete_at=delete_at,
        )
    )
    client = _client(service)

    response = client.get(
        "/api/v1/media/jellyfin/item-1/retention"
    )

    assert response.status_code == 200
    assert response.json()["lifecycle"]["delete_at"] == delete_at


def test_path_identity_is_passed_to_authoritative_service() -> None:
    service = _RetentionService(
        RetentionDecision(
            provider="jellyfin",
            item_id="ABC-123",
            eligible=False,
            policy=PolicyDecision(
                provider="jellyfin",
                item_id="ABC-123",
                action="ignore",
            ),
        )
    )
    client = _client(service)

    response = client.get(
        "/api/v1/media/JELLYFIN/ABC-123/retention"
    )

    assert response.status_code == 200
    assert service.calls == [
        ("JELLYFIN", "ABC-123"),
    ]


def test_response_is_not_time_dependent_in_route_layer() -> None:
    # The route must expose already-evaluated authoritative timestamps.
    # This assertion deliberately uses a timestamp unrelated to wall clock
    # time so a route-layer datetime.now()/timedelta calculation would fail.
    service = _RetentionService(
        _decision(
            basis_at="1999-12-31T23:59:59Z",
            delete_at="2042-01-02T03:04:05Z",
        )
    )
    client = _client(service)

    response = client.get(
        "/api/v1/media/jellyfin/item-1/retention"
    )

    assert response.status_code == 200
    assert response.json()["lifecycle"] == {
        "state": "scheduled",
        "rule": "unwatched_30d",
        "basis_at": "1999-12-31T23:59:59Z",
        "delete_at": "2042-01-02T03:04:05Z",
    }


def test_test_fixture_does_not_depend_on_current_time() -> None:
    # Guard the regression fixture itself against accidental local-time use.
    fixed = datetime(
        2026,
        9,
        14,
        tzinfo=timezone.utc,
    )

    assert fixed.isoformat() == "2026-09-14T00:00:00+00:00"


def test_v1_router_registers_media_retention_route() -> None:
    from atlas_api.routes.v1 import router as v1_router

    app = FastAPI()
    app.include_router(v1_router)

    schema = app.openapi()

    assert (
        "/api/v1/media/{provider}/{item_id}/retention"
        in schema["paths"]
    )


def test_retention_error_returns_stable_unavailable_response() -> None:
    from atlas.retention import RetentionError

    service = _RetentionService(
        RetentionError(
            "private provider failure detail"
        )
    )
    client = _client(service)

    response = client.get(
        "/api/v1/media/jellyfin/item-1/retention"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Media retention state is unavailable."
    }

    assert (
        "private provider failure detail"
        not in response.text
    )


def test_mismatched_authoritative_identity_fails_closed() -> None:
    service = _RetentionService(
        RetentionDecision(
            provider="jellyfin",
            item_id="different-item",
            eligible=False,
            policy=PolicyDecision(
                provider="jellyfin",
                item_id="different-item",
                action="ignore",
            ),
        )
    )
    client = _client(service)

    response = client.get(
        "/api/v1/media/jellyfin/requested-item/retention"
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Media retention state is unavailable."
    }

    assert service.calls == [
        ("jellyfin", "requested-item"),
    ]
