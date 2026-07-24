"""Tests for cleanup execution identity helpers."""

from __future__ import annotations

import unittest

from atlas.cleanup.execution_identity import (
    new_execution_id,
    normalize_execution_id,
)


class CleanupExecutionIdentityTests(unittest.TestCase):
    """Validate cleanup execution identifiers."""

    def test_new_execution_id_uses_supported_format(self) -> None:
        execution_id = new_execution_id()

        self.assertRegex(
            execution_id,
            r"^cln_[0-9a-f]{32}$",
        )

    def test_new_execution_ids_are_unique(self) -> None:
        first = new_execution_id()
        second = new_execution_id()

        self.assertNotEqual(first, second)

    def test_normalizes_whitespace_and_case(self) -> None:
        value = (
            " CLN_0123456789ABCDEF0123456789ABCDEF "
        )

        self.assertEqual(
            normalize_execution_id(value),
            "cln_0123456789abcdef0123456789abcdef",
        )

    def test_rejects_invalid_execution_ids(self) -> None:
        invalid_values = (
            None,
            "",
            " ",
            "cln_short",
            "run_0123456789abcdef0123456789abcdef",
            "cln_0123456789abcdef0123456789abcdeg",
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_execution_id(value)


if __name__ == "__main__":
    unittest.main()
