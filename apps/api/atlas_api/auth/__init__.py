"""Authentication services for the Atlas HTTP API."""

from .exceptions import (
    AuthenticationError,
    AuthenticationProviderError,
    AuthenticationRateLimitError,
    ExpiredTokenError,
    InvalidCredentialsError,
    InvalidTokenError,
    TokenError,
    UnexpectedTokenTypeError,
)
from .hashing import PasswordHasher
from .jwt import JWTService
from .models import (
    AuthenticatedUser,
    TokenClaims,
    TokenPair,
    TokenType,
)
from .service import AuthenticationProvider, AuthenticationService
from .sessions import RefreshSessionRegistry
from .throttling import LoginAttemptLimiter

__all__ = [
    "AuthenticatedUser",
    "AuthenticationError",
    "AuthenticationProvider",
    "AuthenticationProviderError",
    "AuthenticationRateLimitError",
    "AuthenticationService",
    "ExpiredTokenError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "JWTService",
    "LoginAttemptLimiter",
    "PasswordHasher",
    "RefreshSessionRegistry",
    "TokenClaims",
    "TokenError",
    "TokenPair",
    "TokenType",
    "UnexpectedTokenTypeError",
]
