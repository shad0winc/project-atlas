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


class CurrentUserResponse(BaseModel):
    """Authenticated user and effective authorization state."""

    user_id: str
    username: str
    display_name: str
    roles: list[str]
    provider: str
    granted_permission_patterns: list[str]
    denied_permission_patterns: list[str]
