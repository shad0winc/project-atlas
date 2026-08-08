"""Argon2id password hashing for Atlas authentication."""

from __future__ import annotations

from argon2 import PasswordHasher as Argon2PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


class PasswordHasher:
    """Hash and verify passwords using Argon2id."""

    def __init__(self) -> None:
        self._hasher = Argon2PasswordHasher()

    def hash(self, password: str) -> str:
        """Return an Argon2id hash for a plaintext password."""

        _validate_password(password)
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """Return whether a plaintext password matches a stored hash."""

        if not isinstance(password, str) or not password:
            return False

        if not isinstance(password_hash, str) or not password_hash:
            return False

        try:
            return self._hasher.verify(password_hash, password)
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Return whether a stored password hash should be regenerated."""

        if not isinstance(password_hash, str) or not password_hash:
            return True

        try:
            return self._hasher.check_needs_rehash(password_hash)
        except InvalidHashError:
            return True


def _validate_password(password: str) -> None:
    if not isinstance(password, str):
        raise TypeError("Password must be a string.")

    if not password:
        raise ValueError("Password cannot be empty.")
