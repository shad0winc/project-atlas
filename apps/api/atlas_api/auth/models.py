"""Internal authentication models for the Atlas API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class TokenType(StrEnum):
    """Supported Atlas authentication token types."""

    ACCESS = "access"
    REFRESH = "refresh"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    """User identity returned by an authentication provider."""

    user_id: str
    username: str
    display_name: str
    roles: tuple[str, ...] = ()
    provider: str = "atlas"
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("Authenticated user ID cannot be empty.")

        if not self.username.strip():
            raise ValueError("Authenticated username cannot be empty.")

        if not self.display_name.strip():
            raise ValueError("Authenticated display name cannot be empty.")


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Validated claims extracted from an Atlas token."""

    subject: str
    username: str
    roles: tuple[str, ...]
    token_type: TokenType
    token_id: str
    issued_at: int
    expires_at: int


@dataclass(frozen=True, slots=True)
class TokenPair:
    """Access and refresh tokens returned after authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
