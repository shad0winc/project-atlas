"""Contracts for coordinated Atlas/Jellyfin user provisioning."""

from __future__ import annotations

from typing import Any

import pytest

from atlas_api.services.jellyfin_identity import (
    JellyfinIdentityError,
)
from atlas_api.services.user_provisioning import (
    UserProvisioningCompensationError,
    UserProvisioningConflictError,
    UserProvisioningError,
    UserProvisioningService,
)


class FakeProfiles:
    def __init__(
        self,
        users: list[dict[str, Any]] | None = None,
        *,
        create_error: Exception | None = None,
    ) -> None:
        self.users = list(users or [])
        self.create_error = create_error
        self.created: list[dict[str, Any]] = []

    def list_users(self) -> list[dict[str, Any]]:
        return list(self.users)

    def create_user(
        self,
        username: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        if self.create_error is not None:
            raise self.create_error

        profile = {
            "user_id": "atlas-user-1",
            "username": username,
            **kwargs,
        }

        self.created.append(profile)
        self.users.append(profile)

        return profile


class FakeJellyfin:
    def __init__(
        self,
        *,
        create_error: Exception | None = None,
        password_error: Exception | None = None,
        delete_error: Exception | None = None,
    ) -> None:
        self.create_error = create_error
        self.password_error = password_error
        self.delete_error = delete_error

        self.created: list[str] = []
        self.passwords: list[tuple[str, str]] = []
        self.deleted: list[str] = []

    def create_user(self, username: str) -> dict[str, str]:
        if self.create_error is not None:
            raise self.create_error

        self.created.append(username)

        return {
            "id": "ABCDEF1234",
            "name": username,
        }

    def set_password(
        self,
        user_id: str,
        password: str,
    ) -> None:
        if self.password_error is not None:
            raise self.password_error

        self.passwords.append(
            (user_id, password)
        )

    def delete_user(self, user_id: str) -> None:
        if self.delete_error is not None:
            raise self.delete_error

        self.deleted.append(user_id)


def test_success_creates_permanently_linked_atlas_profile() -> None:
    profiles = FakeProfiles()
    jellyfin = FakeJellyfin()

    service = UserProvisioningService(
        profiles,
        jellyfin,
    )

    result = service.provision_user(
        username="Michael",
        email="MICHAEL@example.com",
        password="initial-password",
        roles=("user",),
        display_name="Michael",
        first_name="Michael",
        last_name="Atlas",
    )

    assert jellyfin.created == ["michael"]
    assert jellyfin.passwords == [
        ("abcdef1234", "initial-password")
    ]
    assert jellyfin.deleted == []

    assert result["username"] == "michael"
    assert result["email"] == "michael@example.com"
    assert result["roles"] == ("user",)
    assert result["status"] == "active"
    assert result["jellyfin_user_id"] == "abcdef1234"


def test_existing_username_fails_before_jellyfin_mutation() -> None:
    profiles = FakeProfiles(
        [
            {
                "username": "michael",
                "email": "old@example.com",
            }
        ]
    )
    jellyfin = FakeJellyfin()

    service = UserProvisioningService(
        profiles,
        jellyfin,
    )

    with pytest.raises(
        UserProvisioningConflictError,
        match="Username already exists",
    ):
        service.provision_user(
            username="MICHAEL",
            email="new@example.com",
            password="password",
            roles=("user",),
        )

    assert jellyfin.created == []
    assert jellyfin.passwords == []
    assert jellyfin.deleted == []


def test_existing_email_fails_before_jellyfin_mutation() -> None:
    profiles = FakeProfiles(
        [
            {
                "username": "someone",
                "email": "family@example.com",
            }
        ]
    )
    jellyfin = FakeJellyfin()

    service = UserProvisioningService(
        profiles,
        jellyfin,
    )

    with pytest.raises(
        UserProvisioningConflictError,
        match="Email already exists",
    ):
        service.provision_user(
            username="michael",
            email="FAMILY@example.com",
            password="password",
            roles=("user",),
        )

    assert jellyfin.created == []
    assert jellyfin.passwords == []
    assert jellyfin.deleted == []


def test_jellyfin_create_failure_creates_no_atlas_profile() -> None:
    profiles = FakeProfiles()
    jellyfin = FakeJellyfin(
        create_error=JellyfinIdentityError(
            "create failed",
            status_code=502,
        )
    )

    service = UserProvisioningService(
        profiles,
        jellyfin,
    )

    with pytest.raises(
        UserProvisioningError,
        match="Jellyfin user creation failed",
    ):
        service.provision_user(
            username="michael",
            email="michael@example.com",
            password="password",
            roles=("user",),
        )

    assert profiles.created == []
    assert jellyfin.deleted == []


def test_password_failure_rolls_back_jellyfin_user() -> None:
    profiles = FakeProfiles()
    jellyfin = FakeJellyfin(
        password_error=JellyfinIdentityError(
            "password failed",
            status_code=502,
        )
    )

    service = UserProvisioningService(
        profiles,
        jellyfin,
    )

    with pytest.raises(
        UserProvisioningError,
        match="Jellyfin password provisioning failed",
    ):
        service.provision_user(
            username="michael",
            email="michael@example.com",
            password="password",
            roles=("user",),
        )

    assert profiles.created == []
    assert jellyfin.deleted == ["abcdef1234"]


def test_atlas_profile_failure_rolls_back_jellyfin_user() -> None:
    profiles = FakeProfiles(
        create_error=RuntimeError("store failed")
    )
    jellyfin = FakeJellyfin()

    service = UserProvisioningService(
        profiles,
        jellyfin,
    )

    with pytest.raises(
        UserProvisioningError,
        match="Atlas profile provisioning failed",
    ):
        service.provision_user(
            username="michael",
            email="michael@example.com",
            password="password",
            roles=("user",),
        )

    assert jellyfin.passwords == [
        ("abcdef1234", "password")
    ]
    assert jellyfin.deleted == ["abcdef1234"]


def test_failed_compensation_surfaces_orphan_condition() -> None:
    profiles = FakeProfiles(
        create_error=RuntimeError("store failed")
    )
    jellyfin = FakeJellyfin(
        delete_error=JellyfinIdentityError(
            "delete failed"
        )
    )

    service = UserProvisioningService(
        profiles,
        jellyfin,
    )

    with pytest.raises(
        UserProvisioningCompensationError,
        match="could not be removed",
    ) as captured:
        service.provision_user(
            username="michael",
            email="michael@example.com",
            password="password",
            roles=("user",),
        )

    assert (
        captured.value.jellyfin_user_id
        == "abcdef1234"
    )


@pytest.mark.parametrize(
    ("email", "password", "roles", "message"),
    [
        ("", "password", ("user",), "Email is required"),
        (
            "michael@example.com",
            "",
            ("user",),
            "Password is required",
        ),
        (
            "michael@example.com",
            "password",
            (),
            "At least one role is required",
        ),
    ],
)
def test_required_provisioning_fields_fail_before_mutation(
    email: str,
    password: str,
    roles: tuple[str, ...],
    message: str,
) -> None:
    profiles = FakeProfiles()
    jellyfin = FakeJellyfin()

    service = UserProvisioningService(
        profiles,
        jellyfin,
    )

    with pytest.raises(
        ValueError,
        match=message,
    ):
        service.provision_user(
            username="michael",
            email=email,
            password=password,
            roles=roles,
        )

    assert profiles.created == []
    assert jellyfin.created == []
    assert jellyfin.passwords == []
    assert jellyfin.deleted == []
