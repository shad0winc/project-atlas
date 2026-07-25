"""Exceptions raised by the Atlas Access Control Platform."""


class ACPError(Exception):
    """Base exception for ACP domain failures."""


class ACPValidationError(ACPError, ValueError):
    """Raised when an ACP domain value is invalid."""


class DuplicatePermissionError(ACPError):
    """Raised when a permission identifier is registered twice."""

    def __init__(self, permission: str) -> None:
        self.permission = permission
        super().__init__(
            f"Permission is already registered: {permission}"
        )
