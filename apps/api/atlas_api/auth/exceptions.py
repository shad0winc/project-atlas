"""Authentication-specific exceptions for the Atlas API."""


class AuthenticationError(Exception):
    """Base exception for authentication failures."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when supplied credentials cannot be authenticated."""


class AuthenticationRateLimitError(AuthenticationError):
    """Raised when credential attempts are temporarily throttled."""

    def __init__(self, retry_after_seconds: int) -> None:
        if retry_after_seconds <= 0:
            raise ValueError("Retry-after seconds must be positive.")

        self.retry_after_seconds = retry_after_seconds
        super().__init__("Too many authentication attempts.")


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
