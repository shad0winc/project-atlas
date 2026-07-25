"""Tests for Atlas password hashing."""

import unittest

from atlas_api.auth.hashing import PasswordHasher


class PasswordHasherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.hasher = PasswordHasher()

    def test_hashes_and_verifies_password(self) -> None:
        password_hash = self.hasher.hash("correct horse battery staple")

        self.assertNotEqual(
            password_hash,
            "correct horse battery staple",
        )
        self.assertTrue(
            self.hasher.verify(
                "correct horse battery staple",
                password_hash,
            )
        )

    def test_rejects_wrong_password(self) -> None:
        password_hash = self.hasher.hash("correct password")

        self.assertFalse(
            self.hasher.verify(
                "wrong password",
                password_hash,
            )
        )

    def test_rejects_invalid_hash(self) -> None:
        self.assertFalse(
            self.hasher.verify(
                "password",
                "not-an-argon2-hash",
            )
        )

    def test_rejects_empty_password_for_hashing(self) -> None:
        with self.assertRaises(ValueError):
            self.hasher.hash("")


if __name__ == "__main__":
    unittest.main()
