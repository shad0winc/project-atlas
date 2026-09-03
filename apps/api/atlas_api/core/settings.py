"""Environment-backed settings for the Atlas HTTP API."""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Mapping


class SettingsError(ValueError):
    """Raised when required Atlas API configuration is invalid."""


@dataclass(frozen=True, slots=True)
class AtlasAPISettings:
    """Runtime settings required by the Atlas API authentication layer."""

    jwt_secret: str
    jwt_issuer: str = "project-atlas"
    jwt_audience: str = "atlas-portal"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    base_url: str = "http://localhost"
    password_recovery_minutes: int = 60
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_sender: str = ""
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_security: str = "starttls"

    def __post_init__(self) -> None:
        if not isinstance(self.jwt_secret, str) or len(self.jwt_secret) < 32:
            raise SettingsError(
                "ATLAS_JWT_SECRET must contain at least 32 characters."
            )

        if not self.jwt_issuer.strip():
            raise SettingsError("JWT issuer cannot be empty.")

        if not self.jwt_audience.strip():
            raise SettingsError("JWT audience cannot be empty.")

        if self.access_token_minutes <= 0:
            raise SettingsError("Access-token lifetime must be positive.")

        if self.refresh_token_days <= 0:
            raise SettingsError("Refresh-token lifetime must be positive.")

        if not isinstance(self.base_url, str) or not self.base_url.strip():
            raise SettingsError("ATLAS_BASE_URL cannot be empty.")

        if self.password_recovery_minutes <= 0:
            raise SettingsError(
                "Password-recovery lifetime must be positive."
            )

        if self.smtp_port <= 0:
            raise SettingsError("SMTP port must be positive.")

        if self.smtp_security not in {"starttls", "ssl", "plain"}:
            raise SettingsError(
                "ATLAS_SMTP_SECURITY must be starttls, ssl, or plain."
            )

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "AtlasAPISettings":
        """Create settings from environment variables."""

        values = os.environ if environment is None else environment

        secret = values.get("ATLAS_JWT_SECRET", "")
        issuer = values.get("ATLAS_JWT_ISSUER", "project-atlas")
        audience = values.get("ATLAS_JWT_AUDIENCE", "atlas-portal")

        access_minutes = _read_positive_integer(
            values,
            "ATLAS_ACCESS_TOKEN_MINUTES",
            default=15,
        )
        refresh_days = _read_positive_integer(
            values,
            "ATLAS_REFRESH_TOKEN_DAYS",
            default=30,
        )

        base_url = values.get(
            "ATLAS_BASE_URL",
            "http://localhost",
        ).strip().rstrip("/")

        recovery_minutes = _read_positive_integer(
            values,
            "ATLAS_PASSWORD_RECOVERY_MINUTES",
            default=60,
        )

        smtp_host = values.get("ATLAS_SMTP_HOST", "").strip()
        smtp_port = _read_positive_integer(
            values,
            "ATLAS_SMTP_PORT",
            default=587,
        )
        smtp_sender = values.get("ATLAS_SMTP_SENDER", "").strip()
        smtp_username = values.get("ATLAS_SMTP_USERNAME", "").strip()
        smtp_password = values.get("ATLAS_SMTP_PASSWORD", "")
        smtp_security = values.get(
            "ATLAS_SMTP_SECURITY",
            "starttls",
        ).strip().lower()

        return cls(
            jwt_secret=secret,
            jwt_issuer=issuer,
            jwt_audience=audience,
            access_token_minutes=access_minutes,
            refresh_token_days=refresh_days,
            base_url=base_url,
            password_recovery_minutes=recovery_minutes,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_sender=smtp_sender,
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            smtp_security=smtp_security,
        )


def _read_positive_integer(
    environment: Mapping[str, str],
    name: str,
    *,
    default: int,
) -> int:
    raw_value = environment.get(name)

    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as error:
        raise SettingsError(f"{name} must be an integer.") from error

    if value <= 0:
        raise SettingsError(f"{name} must be greater than zero.")

    return value
