"""Authentication-specific exceptions for the Atlas API."""


class AuthenticationError(Exception):
    """Base exception for authentication failures."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when supplied credentials cannot be authenticated."""


class AuthenticationProviderError(AuthenticationError):
    """Raised when an authentication provider cannot complete a request."""


class TokenError(AuthenticationError):
    """Base exception for token failures."""


class InvalidTokenError(TokenError):
    """Raised when a token is malformed or cryptographically invalid."""


class ExpiredTokenError(TokenError):
    """Raised when a token has expired."""


class UnexpectedTokenTypeError(TokenError):
    """Raised when a token is valid but has the wrong token type."""
