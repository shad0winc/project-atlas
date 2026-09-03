"""Atlas password-recovery orchestration."""

from __future__ import annotations

from datetime import timedelta
from threading import RLock
from typing import Callable
from urllib.parse import quote

from atlas.password_recovery import (
    PasswordRecoveryError,
    PasswordRecoveryStore,
)
from atlas.user_profiles import (
    UserProfileStore,
    normalize_email,
)
from atlas_api.auth.sessions import RefreshSessionRegistry
from atlas_api.auth.throttling import PasswordRecoveryRequestLimiter
from atlas_api.services.email_sender import (
    EmailDeliveryError,
    SMTPEmailSender,
)
from atlas_api.services.identity_writer import (
    IdentityWriterClient,
    IdentityWriterError,
)


_RECOVERY_FLOW_LOCK = RLock()


class PasswordRecoveryServiceError(RuntimeError):
    """A recovery operation could not be completed safely."""


AuditPublisher = Callable[
    [str, dict[str, object]],
    None,
]


class PasswordRecoveryService:
    """Issue and consume durable one-time password resets."""

    def __init__(
        self,
        *,
        users: UserProfileStore,
        recoveries: PasswordRecoveryStore,
        identity_writer: IdentityWriterClient,
        email_sender: SMTPEmailSender,
        base_url: str,
        expires_minutes: int = 60,
        audit_publisher: AuditPublisher | None = None,
        request_limiter: PasswordRecoveryRequestLimiter | None = None,
        refresh_sessions: RefreshSessionRegistry | None = None,
    ) -> None:
        self._users = users
        self._recoveries = recoveries
        self._identity_writer = identity_writer
        self._email_sender = email_sender
        self._base_url = base_url.rstrip("/")
        self._expires_minutes = expires_minutes
        self._audit = audit_publisher
        self._request_limiter = (
            request_limiter
            if request_limiter is not None
            else PasswordRecoveryRequestLimiter()
        )
        self._refresh_sessions = (
            refresh_sessions
            if refresh_sessions is not None
            else RefreshSessionRegistry()
        )

        if not self._base_url:
            raise ValueError("Atlas base URL is required.")
        if self._expires_minutes <= 0:
            raise ValueError(
                "Password recovery lifetime must be positive."
            )

    def request_reset(self, email: str) -> None:
        """Request recovery without revealing account existence."""

        with _RECOVERY_FLOW_LOCK:
            self._request_reset(email)

    def _request_reset(self, email: str) -> None:
        try:
            normalized_email = normalize_email(email)
        except Exception:
            self._publish(
                "security.identity.password_recovery_requested",
                {
                    "matched": False,
                    "delivery": "not-attempted",
                },
            )
            return

        if not normalized_email:
            self._publish(
                "security.identity.password_recovery_requested",
                {
                    "matched": False,
                    "delivery": "not-attempted",
                },
            )
            return

        retry_after = self._request_limiter.retry_after(
            normalized_email
        )

        if retry_after is not None:
            self._publish(
                "security.identity.password_recovery_requested",
                {
                    "delivery": "suppressed",
                    "reason": "rate-limit",
                    "retry_after_seconds": retry_after,
                },
            )
            return

        self._request_limiter.record(normalized_email)

        profile = self._find_active_profile_by_email(
            normalized_email
        )

        if profile is None:
            self._publish(
                "security.identity.password_recovery_requested",
                {
                    "matched": False,
                    "delivery": "not-attempted",
                },
            )
            return

        issue = self._recoveries.create(
            user_id=str(profile["user_id"]),
            expires_in=timedelta(
                minutes=self._expires_minutes
            ),
        )

        reset_url = (
            f"{self._base_url}/reset-password"
            f"#token={quote(issue.token, safe='')}"
        )

        try:
            self._email_sender.send_password_reset(
                recipient=normalized_email,
                reset_url=reset_url,
                expires_minutes=self._expires_minutes,
            )
        except EmailDeliveryError:
            self._recoveries.revoke(
                issue.recovery["recovery_id"]
            )
            self._publish(
                "security.identity.password_recovery_requested",
                {
                    "matched": True,
                    "delivery": "failed",
                    "user_id": str(profile["user_id"]),
                },
            )
            return

        self._publish(
            "security.identity.password_recovery_requested",
            {
                "matched": True,
                "delivery": "sent",
                "user_id": str(profile["user_id"]),
            },
        )

    def reset_password(
        self,
        *,
        token: str,
        new_password: str,
    ) -> None:
        """Apply a Jellyfin-backed password then consume the token."""

        with _RECOVERY_FLOW_LOCK:
            self._reset_password(
                token=token,
                new_password=new_password,
            )

    def _reset_password(
        self,
        *,
        token: str,
        new_password: str,
    ) -> None:
        if not isinstance(new_password, str) or not new_password:
            raise PasswordRecoveryServiceError(
                "New password is required."
            )

        try:
            record = self._recoveries.verify_token(token)
        except PasswordRecoveryError as error:
            self._publish(
                "security.identity.password_recovery_rejected",
                {"reason": "invalid-or-expired"},
            )
            raise PasswordRecoveryServiceError(
                "Password recovery token is invalid or expired."
            ) from error

        user_id = str(record["user_id"])

        try:
            profile = self._users.get_user(user_id)
        except Exception as error:
            self._publish(
                "security.identity.password_recovery_rejected",
                {
                    "reason": "user-unavailable",
                    "user_id": user_id,
                },
            )
            raise PasswordRecoveryServiceError(
                "Password recovery cannot be completed."
            ) from error

        if str(profile.get("status") or "") != "active":
            self._publish(
                "security.identity.password_recovery_rejected",
                {
                    "reason": "user-inactive",
                    "user_id": user_id,
                },
            )
            raise PasswordRecoveryServiceError(
                "Password recovery cannot be completed."
            )

        try:
            self._identity_writer.set_user_password(
                user_id,
                new_password,
            )
        except IdentityWriterError as error:
            self._publish(
                "security.identity.password_recovery_failed",
                {
                    "reason": "identity-writer",
                    "user_id": user_id,
                },
            )
            raise PasswordRecoveryServiceError(
                "Password recovery cannot be completed."
            ) from error

        revoked_refresh_sessions = (
            self._refresh_sessions.revoke_subject(user_id)
        )

        try:
            self._recoveries.complete(
                str(record["recovery_id"])
            )
        except PasswordRecoveryError as error:
            self._publish(
                "security.identity.password_recovery_failed",
                {
                    "reason": "token-finalization",
                    "user_id": user_id,
                },
            )
            raise PasswordRecoveryServiceError(
                "Password was changed but recovery state "
                "could not be finalized."
            ) from error

        self._publish(
            "security.identity.password_recovery_completed",
            {
                "user_id": user_id,
                "revoked_refresh_sessions": revoked_refresh_sessions,
            },
        )

    def _find_active_profile_by_email(
        self,
        normalized_email: str,
    ) -> dict[str, object] | None:
        for profile in self._users.list_users():
            if (
                profile.get("email") == normalized_email
                and profile.get("status") == "active"
            ):
                return profile
        return None

    def _publish(
        self,
        event: str,
        payload: dict[str, object],
    ) -> None:
        if self._audit is not None:
            self._audit(event, payload)
