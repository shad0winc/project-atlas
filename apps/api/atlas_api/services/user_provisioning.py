"""Coordinated Atlas and Jellyfin user provisioning.

The provisioning service owns the cross-system lifecycle transaction for
new Atlas identities. It creates the Jellyfin companion identity first and
compensates by deleting that Jellyfin identity if a later provisioning step
fails.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from atlas.user_profiles import normalize_email, normalize_username
from atlas_api.services.jellyfin_identity import (
    JellyfinIdentityError,
)


class UserProfileWriter(Protocol):
    """Minimal Atlas profile-store surface required for provisioning."""

    def list_users(self) -> list[dict[str, Any]]:
        """Return existing Atlas profiles."""

    def create_user(
        self,
        username: str,
        *,
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        discord_account: str | None = None,
        email_notifications_enabled: bool = False,
        discord_notifications_enabled: bool = False,
        roles: Sequence[str] | None = None,
        status: str = "active",
        jellyfin_user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create one Atlas profile."""


class JellyfinIdentityProvisioner(Protocol):
    """Minimal Jellyfin identity lifecycle surface."""

    def create_user(self, username: str) -> dict[str, str]:
        """Create one Jellyfin user."""

    def set_password(self, user_id: str, password: str) -> None:
        """Set one Jellyfin user's password."""

    def delete_user(self, user_id: str) -> None:
        """Delete one Jellyfin user."""


class UserProvisioningError(RuntimeError):
    """Atlas/Jellyfin user provisioning failed."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 502,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


class UserProvisioningConflictError(UserProvisioningError):
    """Requested Atlas identity conflicts with an existing profile."""


class UserProvisioningCompensationError(UserProvisioningError):
    """Provisioning failed and Jellyfin compensation also failed."""

    def __init__(
        self,
        message: str,
        *,
        jellyfin_user_id: str,
    ) -> None:
        super().__init__(
            message,
            status_code=500,
        )
        self.jellyfin_user_id = jellyfin_user_id


class UserProvisioningService:
    """Provision one permanently linked Atlas/Jellyfin identity."""

    def __init__(
        self,
        profiles: UserProfileWriter,
        jellyfin: JellyfinIdentityProvisioner,
    ) -> None:
        self._profiles = profiles
        self._jellyfin = jellyfin

    def provision_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        roles: Sequence[str],
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        discord_account: str | None = None,
        email_notifications_enabled: bool = False,
        discord_notifications_enabled: bool = False,
    ) -> dict[str, Any]:
        """Create a Jellyfin user and linked Atlas profile.

        Email is mandatory for this provisioning path even though the lower
        level Atlas profile store remains backward-compatible with profiles
        that do not have an email address.
        """

        normalized_username = normalize_username(username)
        normalized_email = normalize_email(email)

        if normalized_email is None:
            raise ValueError(
                "Email is required for Atlas user provisioning."
            )

        if not isinstance(password, str) or not password:
            raise ValueError(
                "Password is required for Atlas user provisioning."
            )

        normalized_roles = tuple(
            str(role).strip()
            for role in roles
            if str(role).strip()
        )

        if not normalized_roles:
            raise ValueError(
                "At least one role is required for Atlas user provisioning."
            )

        self._assert_available(
            normalized_username,
            normalized_email,
        )

        try:
            jellyfin_user = self._jellyfin.create_user(
                normalized_username
            )
        except JellyfinIdentityError as error:
            raise UserProvisioningError(
                "Jellyfin user creation failed.",
                status_code=error.status_code,
            ) from error

        jellyfin_user_id = self._required_jellyfin_id(
            jellyfin_user
        )

        try:
            self._jellyfin.set_password(
                jellyfin_user_id,
                password,
            )

            return self._profiles.create_user(
                normalized_username,
                display_name=display_name,
                first_name=first_name,
                last_name=last_name,
                email=normalized_email,
                discord_account=discord_account,
                email_notifications_enabled=(
                    email_notifications_enabled
                ),
                discord_notifications_enabled=(
                    discord_notifications_enabled
                ),
                roles=normalized_roles,
                status="active",
                jellyfin_user_id=jellyfin_user_id,
            )
        except Exception as error:
            self._compensate_or_raise(
                jellyfin_user_id,
                original_error=error,
            )

            if isinstance(error, UserProvisioningError):
                raise

            if isinstance(error, JellyfinIdentityError):
                raise UserProvisioningError(
                    "Jellyfin password provisioning failed.",
                    status_code=error.status_code,
                ) from error

            raise UserProvisioningError(
                "Atlas profile provisioning failed.",
                status_code=409,
            ) from error

    def _assert_available(
        self,
        username: str,
        email: str,
    ) -> None:
        for profile in self._profiles.list_users():
            existing_username = profile.get("username")

            if (
                isinstance(existing_username, str)
                and normalize_username(existing_username) == username
            ):
                raise UserProvisioningConflictError(
                    "Username already exists.",
                    status_code=409,
                )

            existing_email = normalize_email(
                profile.get("email")
            )

            if existing_email == email:
                raise UserProvisioningConflictError(
                    "Email already exists.",
                    status_code=409,
                )

    def _compensate_or_raise(
        self,
        jellyfin_user_id: str,
        *,
        original_error: Exception,
    ) -> None:
        try:
            self._jellyfin.delete_user(jellyfin_user_id)
        except Exception as compensation_error:
            raise UserProvisioningCompensationError(
                (
                    "User provisioning failed and the newly created "
                    "Jellyfin identity could not be removed."
                ),
                jellyfin_user_id=jellyfin_user_id,
            ) from compensation_error

    @staticmethod
    def _required_jellyfin_id(
        user: Mapping[str, Any],
    ) -> str:
        value = user.get("id")

        if not isinstance(value, str) or not value.strip():
            raise UserProvisioningError(
                "Jellyfin creation did not return a usable user ID."
            )

        return value.strip().lower()


__all__ = [
    "JellyfinIdentityProvisioner",
    "UserProfileWriter",
    "UserProvisioningCompensationError",
    "UserProvisioningConflictError",
    "UserProvisioningError",
    "UserProvisioningService",
]
