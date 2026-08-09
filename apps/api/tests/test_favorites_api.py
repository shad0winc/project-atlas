"""Security and contract tests for the authenticated Favorites API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import unittest

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas.favorite_service import FavoriteMutationResult
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.main import create_app
from atlas_api.routes.v1.favorites import (
    get_favorites_api_service,
    require_favorites_read,
    require_favorites_write,
)
from atlas_api.services.favorites import (
    FavoriteNotFoundError,
    FavoritesAPIService,
)


USER_ID = "usr_" + ("a" * 32)
OTHER_USER_ID = "usr_" + ("b" * 32)
FAVORITE_ID = "fav_" + ("c" * 32)


def favorite_record(
    *,
    user_id: str = USER_ID,
    favorite_id: str = FAVORITE_ID,
) -> dict[str, Any]:
    """Return one valid serialized Favorite record."""

    return {
        "schema_version": 1,
        "favorite_id": favorite_id,
        "user_id": user_id,
        "provider": "jellyfin",
        "item_id": "jellyfin-item-1",
        "media_type": "movie",
        "title": "Atlas Test Movie",
        "metadata": {},
        "created_at": "2026-08-09T20:00:00Z",
        "updated_at": "2026-08-09T20:00:00Z",
    }


def authenticated_user() -> AuthenticatedUser:
    """Return a stable self-scoped user for route tests."""

    return AuthenticatedUser(
        user_id=USER_ID,
        username="michael",
        display_name="Michael",
        roles=("member",),
        provider="jellyfin",
        metadata={},
    )


class StubFavoritesAPIService:
    """Record route-to-service calls without touching persistent state."""

    def __init__(self) -> None:
        self.records = [
            favorite_record()
        ]
        self.list_user_ids: list[str] = []
        self.add_calls: list[
            tuple[str, str, str, dict[str, Any] | None]
        ] = []
        self.remove_calls: list[
            tuple[str, str]
        ] = []

    def list_for_user(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        self.list_user_ids.append(
            user_id
        )
        return list(self.records)

    def add_for_user(
        self,
        user_id: str,
        provider: str,
        item_id: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> FavoriteMutationResult:
        self.add_calls.append(
            (
                user_id,
                provider,
                item_id,
                metadata,
            )
        )

        record = favorite_record()
        record["provider"] = provider
        record["item_id"] = item_id
        record["metadata"] = dict(
            metadata or {}
        )

        return FavoriteMutationResult(
            record=record
        )

    def remove_for_user(
        self,
        user_id: str,
        favorite_id: str,
    ) -> FavoriteMutationResult:
        self.remove_calls.append(
            (
                user_id,
                favorite_id,
            )
        )

        return FavoriteMutationResult(
            record=favorite_record(
                favorite_id=favorite_id
            )
        )


class FavoritesEndpointTests(unittest.TestCase):
    """Verify the authenticated, self-scoped Favorites routes."""

    def setUp(self) -> None:
        self.app = create_app()
        self.service = StubFavoritesAPIService()

        self.app.dependency_overrides[
            require_favorites_read
        ] = authenticated_user

        self.app.dependency_overrides[
            require_favorites_write
        ] = authenticated_user

        self.app.dependency_overrides[
            get_favorites_api_service
        ] = lambda: self.service

        self.client = TestClient(
            self.app
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_list_uses_authenticated_user_scope(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/favorites"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            [USER_ID],
            self.service.list_user_ids,
        )

        self.assertEqual(
            USER_ID,
            response.json()["favorites"][0]["user_id"],
        )

    def test_create_uses_authenticated_user_scope(
        self,
    ) -> None:
        response = self.client.post(
            "/api/v1/favorites",
            json={
                "provider": "jellyfin",
                "item_id": "jellyfin-item-2",
            },
        )

        self.assertEqual(
            201,
            response.status_code,
        )

        self.assertEqual(
            [
                (
                    USER_ID,
                    "jellyfin",
                    "jellyfin-item-2",
                    None,
                )
            ],
            self.service.add_calls,
        )

    def test_create_rejects_caller_supplied_metadata(
        self,
    ) -> None:
        response = self.client.post(
            "/api/v1/favorites",
            json={
                "provider": "jellyfin",
                "item_id": "jellyfin-item-2",
                "metadata": {
                    "privileged": True,
                },
            },
        )

        self.assertEqual(
            422,
            response.status_code,
        )

        self.assertEqual(
            [],
            self.service.add_calls,
        )

    def test_create_rejects_caller_supplied_user_id(
        self,
    ) -> None:
        response = self.client.post(
            "/api/v1/favorites",
            json={
                "user_id": OTHER_USER_ID,
                "provider": "jellyfin",
                "item_id": "jellyfin-item-2",
            },
        )

        self.assertEqual(
            422,
            response.status_code,
        )

        self.assertEqual(
            [],
            self.service.add_calls,
        )

    def test_delete_uses_authenticated_user_scope(
        self,
    ) -> None:
        response = self.client.delete(
            f"/api/v1/favorites/{FAVORITE_ID}"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            [
                (
                    USER_ID,
                    FAVORITE_ID,
                )
            ],
            self.service.remove_calls,
        )

    def test_read_requires_authentication(
        self,
    ) -> None:
        def unauthenticated() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication is required.",
                headers={
                    "WWW-Authenticate": "Bearer"
                },
            )

        self.app.dependency_overrides[
            require_favorites_read
        ] = unauthenticated

        response = self.client.get(
            "/api/v1/favorites"
        )

        self.assertEqual(
            401,
            response.status_code,
        )

        self.assertEqual(
            "Bearer",
            response.headers["www-authenticate"],
        )

    def test_write_rejects_missing_permission(
        self,
    ) -> None:
        def forbidden() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "No assigned role or direct grant "
                    "provides the requested permission."
                ),
            )

        self.app.dependency_overrides[
            require_favorites_write
        ] = forbidden

        response = self.client.post(
            "/api/v1/favorites",
            json={
                "provider": "jellyfin",
                "item_id": "jellyfin-item-2",
            },
        )

        self.assertEqual(
            403,
            response.status_code,
        )

        self.assertEqual(
            [],
            self.service.add_calls,
        )

    def test_openapi_registers_favorites_routes(
        self,
    ) -> None:
        schema = self.client.app.openapi()

        self.assertIn(
            "/api/v1/favorites",
            schema["paths"],
        )

        self.assertIn(
            "/api/v1/favorites/{favorite_id}",
            schema["paths"],
        )


class FakeStore:
    """Minimal storage double for self-scope security tests."""

    def __init__(
        self,
        record: dict[str, Any],
    ) -> None:
        self.record = dict(record)

    def get(
        self,
        _favorite_id: str,
    ) -> dict[str, Any]:
        return dict(self.record)

    def list(
        self,
        *,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if self.record["user_id"] != user_id:
            return []
        return [
            dict(self.record)
        ]


@dataclass
class FakeMutations:
    """Mutation double that records whether removal was attempted."""

    remove_calls: int = 0

    def remove(
        self,
        favorite_id: str,
    ) -> FavoriteMutationResult:
        self.remove_calls += 1
        return FavoriteMutationResult(
            record=favorite_record(
                favorite_id=favorite_id
            )
        )


class FavoritesServiceSecurityTests(
    unittest.TestCase
):
    """Protect ownership boundaries below the HTTP layer."""

    def test_cross_user_delete_is_hidden_as_not_found(
        self,
    ) -> None:
        store = FakeStore(
            favorite_record(
                user_id=OTHER_USER_ID
            )
        )

        mutations = FakeMutations()

        service = FavoritesAPIService(
            store=store,  # type: ignore[arg-type]
            mutations=mutations,  # type: ignore[arg-type]
        )

        with self.assertRaises(
            FavoriteNotFoundError
        ):
            service.remove_for_user(
                USER_ID,
                FAVORITE_ID,
            )

        self.assertEqual(
            0,
            mutations.remove_calls,
        )


if __name__ == "__main__":
    unittest.main()
