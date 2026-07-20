"""Tests for provider-neutral media mutation contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from enum import Enum
import unittest

from atlas.media import (
    MediaProvider,
    ProviderMutationError,
    ProviderMutationResult,
    ProviderOperation,
)


def _result(
    **overrides: object,
) -> ProviderMutationResult:
    values: dict[str, object] = {
        "provider": "jellyfin",
        "operation": ProviderOperation.DELETE,
        "item_id": "movie-123",
        "success": True,
        "message": "Deletion recorded",
        "executed_at": "2026-07-20T18:30:00Z",
    }
    values.update(overrides)

    return ProviderMutationResult(**values)  # type: ignore[arg-type]


class ProviderMutationContractTests(unittest.TestCase):
    def test_provider_operation_is_string_enum(self) -> None:
        self.assertTrue(issubclass(ProviderOperation, str))
        self.assertTrue(issubclass(ProviderOperation, Enum))
        self.assertEqual(
            ProviderOperation.DELETE.value,
            "delete",
        )

    def test_mutation_result_normalizes_values(self) -> None:
        result = _result(
            provider="  Jellyfin  ",
            operation="delete",
            item_id="  movie-123  ",
            message="  Deletion recorded  ",
            executed_at="2026-07-20T14:30:00-04:00",
        )

        self.assertEqual(result.provider, "jellyfin")
        self.assertIs(
            result.operation,
            ProviderOperation.DELETE,
        )
        self.assertEqual(result.item_id, "movie-123")
        self.assertEqual(
            result.message,
            "Deletion recorded",
        )
        self.assertEqual(
            result.executed_at,
            "2026-07-20T18:30:00Z",
        )

    def test_mutation_result_serializes_to_dict(self) -> None:
        result = _result()

        self.assertEqual(
            result.to_dict(),
            {
                "provider": "jellyfin",
                "operation": "delete",
                "item_id": "movie-123",
                "success": True,
                "message": "Deletion recorded",
                "executed_at": "2026-07-20T18:30:00Z",
            },
        )

    def test_mutation_result_is_immutable(self) -> None:
        result = _result()

        with self.assertRaises(FrozenInstanceError):
            result.provider = "plex"  # type: ignore[misc]

    def test_required_text_fields_reject_invalid_values(self) -> None:
        cases = (
            ("provider", ""),
            ("provider", "   "),
            ("provider", None),
            ("item_id", ""),
            ("item_id", "   "),
            ("item_id", None),
            ("message", ""),
            ("message", "   "),
            ("message", None),
        )

        for field_name, value in cases:
            with self.subTest(
                field_name=field_name,
                value=value,
            ):
                with self.assertRaisesRegex(
                    ProviderMutationError,
                    rf"{field_name} is required",
                ):
                    _result(**{field_name: value})

    def test_invalid_operation_is_rejected(self) -> None:
        for operation in ("", "archive", None, 42):
            with self.subTest(operation=operation):
                with self.assertRaisesRegex(
                    ProviderMutationError,
                    "invalid provider operation",
                ):
                    _result(operation=operation)

    def test_success_requires_boolean(self) -> None:
        for success in (1, 0, "true", None):
            with self.subTest(success=success):
                with self.assertRaisesRegex(
                    ProviderMutationError,
                    "success must be a boolean",
                ):
                    _result(success=success)

    def test_invalid_timestamp_is_rejected(self) -> None:
        for executed_at in (
            "",
            "not-a-timestamp",
            "2026-07-20T18:30:00",
            None,
        ):
            with self.subTest(executed_at=executed_at):
                with self.assertRaisesRegex(
                    ProviderMutationError,
                    "executed_at",
                ):
                    _result(executed_at=executed_at)

    def test_media_provider_exposes_safe_delete_preview(self) -> None:
        self.assertTrue(
            hasattr(
                MediaProvider,
                "preview_delete_item",
            )
        )
        self.assertFalse(
            hasattr(
                MediaProvider,
                "delete_item",
            )
        )


if __name__ == "__main__":
    unittest.main()
