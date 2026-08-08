"""Authentication services for the Atlas HTTP API."""

from .exceptions import (
    AuthenticationError,
    AuthenticationProviderError,
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

__all__ = [
    "AuthenticatedUser",
    "AuthenticationError",
    "AuthenticationProvider",
    "AuthenticationProviderError",
    "AuthenticationService",
    "ExpiredTokenError",
    "InvalidCredentialsError",
    "InvalidTokenError",
    "JWTService",
    "PasswordHasher",
    "TokenClaims",
    "TokenError",
    "TokenPair",
    "TokenType",
    "UnexpectedTokenTypeError",
]
