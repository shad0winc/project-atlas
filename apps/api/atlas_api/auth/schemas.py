"""Pydantic transport schemas for Atlas authentication."""

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Credentials submitted to the Atlas login endpoint."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class RefreshRequest(BaseModel):
    """Refresh token submitted for token rotation."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """Token pair returned by Atlas authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UpdateCurrentUserRequest(BaseModel):
    """Supported self-service Atlas profile fields."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=100)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
    email: str | None = Field(default=None, max_length=320)
    discord_account: str | None = Field(default=None, max_length=200)
    email_notifications_enabled: bool | None = None
    discord_notifications_enabled: bool | None = None


class CurrentUserResponse(BaseModel):
    """Authenticated user and effective authorization state."""

    user_id: str
    username: str
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    discord_account: str | None = None
    email_notifications_enabled: bool = False
    discord_notifications_enabled: bool = False
    roles: list[str]
    provider: str
    granted_permission_patterns: list[str]
    denied_permission_patterns: list[str]

class PasswordRecoveryRequest(BaseModel):
    """Unauthenticated password-recovery request."""

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=1, max_length=254)


class PasswordRecoveryResetRequest(BaseModel):
    """Consume one password-recovery token."""

    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)
