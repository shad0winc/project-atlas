"""Transactional invitation redemption and Atlas user registration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from atlas.invitations import InvitationError, InvitationStore
from atlas.user_profiles import (
    UserProfileError,
    UserProfileStore,
    normalize_email,
    normalize_jellyfin_user_id,
)


class RegistrationError(RuntimeError):
    """Raised when a registration transaction cannot be completed."""

    def __init__(self, message: str, *, rollback_errors: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.rollback_errors = rollback_errors


class UserProvisioner(Protocol):
    """External account provider used by the registration transaction."""

    def create_user(
        self,
        *,
        username: str,
        password: str,
        email: str | None,
        display_name: str | None,
        role: str,
    ) -> str:
        """Create an external account and return its stable user identifier."""

    def delete_user(self, user_id: str) -> None:
        """Delete an externally provisioned account during compensation."""


EventPublisher = Callable[[str, Mapping[str, Any]], None]


@dataclass(frozen=True)
class RegistrationResult:
    """Successful registration result returned to CLI or portal callers."""

    invitation: dict[str, Any]
    profile: dict[str, Any]
    external_user_id: str
    event_error: str | None = None


@dataclass(frozen=True)
class RegistrationService:
    """Coordinate invitation, profile, and external-account state."""

    invitations: InvitationStore
    profiles: UserProfileStore
    provisioner: UserProvisioner
    event_publisher: EventPublisher | None = None

    def register(
        self,
        *,
        token: str,
        username: str,
        password: str,
        email: str | None = None,
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        birthday: str | None = None,
    ) -> RegistrationResult:
        """Redeem one invitation and create linked external and Atlas users.

        The plaintext password is passed directly to the external provisioner
        and is never persisted by Atlas.
        """
        if not isinstance(password, str) or not password:
            raise RegistrationError("password is required")

        try:
            invitation = self.invitations.verify_token(token)
            registration_email = self._registration_email(invitation, email)
        except (InvitationError, UserProfileError) as exc:
            raise RegistrationError(str(exc)) from exc

        external_user_id: str | None = None
        profile: dict[str, Any] | None = None
        rollback_errors: list[str] = []

        try:
            external_user_id = normalize_jellyfin_user_id(
                self.provisioner.create_user(
                    username=username,
                    password=password,
                    email=registration_email,
                    display_name=display_name,
                    role=invitation["role"],
                )
            )
            if external_user_id is None:
                raise RegistrationError("provisioner returned an empty user ID")

            profile = self.profiles.create_user(
                username,
                display_name=display_name,
                first_name=first_name,
                last_name=last_name,
                email=registration_email,
                birthday=birthday,
                role=invitation["role"],
                jellyfin_user_id=external_user_id,
            )
            completed = self.invitations.complete(
                invitation["invite_id"],
                completed_by=profile["user_id"],
            )
        except Exception as exc:
            if profile is not None:
                try:
                    self.profiles.delete_user(profile["user_id"])
                except Exception as rollback_exc:  # pragma: no cover - defensive
                    rollback_errors.append(f"Atlas profile rollback failed: {rollback_exc}")
            if external_user_id is not None:
                try:
                    self.provisioner.delete_user(external_user_id)
                except Exception as rollback_exc:  # pragma: no cover - defensive
                    rollback_errors.append(f"external user rollback failed: {rollback_exc}")
            message = str(exc) or exc.__class__.__name__
            raise RegistrationError(message, rollback_errors=tuple(rollback_errors)) from exc

        event_error = self._publish_registration_event(completed, profile)
        return RegistrationResult(
            invitation=completed,
            profile=profile,
            external_user_id=external_user_id,
            event_error=event_error,
        )

    @staticmethod
    def _registration_email(
        invitation: Mapping[str, Any], supplied_email: str | None
    ) -> str | None:
        invited_email = normalize_email(invitation.get("email"))
        normalized_supplied = normalize_email(supplied_email)
        if invited_email and normalized_supplied and invited_email != normalized_supplied:
            raise RegistrationError("registration email does not match invitation")
        return invited_email or normalized_supplied

    def _publish_registration_event(
        self,
        invitation: Mapping[str, Any],
        profile: Mapping[str, Any],
    ) -> str | None:
        if self.event_publisher is None:
            return None
        payload = {
            "invite_id": invitation["invite_id"],
            "user_id": profile["user_id"],
            "username": profile["username"],
            "role": profile["role"],
            "jellyfin_user_id": profile["jellyfin_user_id"],
        }
        try:
            self.event_publisher("identity.registration.completed", payload)
        except Exception as exc:  # event delivery must not undo registration
            return str(exc) or exc.__class__.__name__
        return None
