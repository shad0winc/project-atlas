"""Tests for provider capability contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from enum import Enum
import unittest

from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
    ProviderCapabilityError,
)


def _capabilities(
    **overrides: object,
) -> ProviderCapabilities:
    values: dict[str, object] = {
        "provider": "jellyfin",
        "capabilities": frozenset(
            {
                ProviderCapability.LIST_MEDIA,
                ProviderCapability.PREVIEW_DELETE,
            }
        ),
        "supports_batch_listing": True,
        "supports_batch_preview": False,
        "max_batch_size": 200,
    }
    values.update(overrides)

    return ProviderCapabilities(
        **values,  # type: ignore[arg-type]
    )


class ProviderCapabilityTests(unittest.TestCase):
    def test_capability_is_string_enum(self) -> None:
        self.assertTrue(
            issubclass(
                ProviderCapability,
                str,
            )
        )
        self.assertTrue(
            issubclass(
                ProviderCapability,
                Enum,
            )
        )
        self.assertEqual(
            ProviderCapability.LIST_MEDIA.value,
            "list_media",
        )

    def test_all_expected_capabilities_are_available(
        self,
    ) -> None:
        self.assertEqual(
            {
                capability.value
                for capability in ProviderCapability
            },
            {
                "list_media",
                "preview_delete",
                "delete",
                "restore",
            },
        )


class ProviderCapabilitiesTests(unittest.TestCase):
    def test_normalizes_provider_and_capabilities(
        self,
    ) -> None:
        capabilities = _capabilities(
            provider="  Jellyfin  ",
            capabilities=frozenset(
                {
                    "list_media",
                    "preview_delete",
                }
            ),
        )

        self.assertEqual(
            capabilities.provider,
            "jellyfin",
        )
        self.assertEqual(
            capabilities.capabilities,
            frozenset(
                {
                    ProviderCapability.LIST_MEDIA,
                    ProviderCapability.PREVIEW_DELETE,
                }
            ),
        )

    def test_contract_is_immutable(self) -> None:
        capabilities = _capabilities()

        with self.assertRaises(FrozenInstanceError):
            capabilities.provider = "plex"  # type: ignore[misc]

    def test_supports_known_capability(self) -> None:
        capabilities = _capabilities()

        self.assertTrue(
            capabilities.supports(
                ProviderCapability.LIST_MEDIA
            )
        )
        self.assertTrue(
            capabilities.supports(
                "preview_delete"
            )
        )
        self.assertFalse(
            capabilities.supports(
                ProviderCapability.DELETE
            )
        )

    def test_supports_rejects_invalid_capability(
        self,
    ) -> None:
        capabilities = _capabilities()

        with self.assertRaisesRegex(
            ProviderCapabilityError,
            "invalid provider capability",
        ):
            capabilities.supports("archive")

    def test_serializes_to_dict(self) -> None:
        capabilities = _capabilities()

        self.assertEqual(
            capabilities.to_dict(),
            {
                "provider": "jellyfin",
                "capabilities": [
                    "list_media",
                    "preview_delete",
                ],
                "supports_batch_listing": True,
                "supports_batch_preview": False,
                "max_batch_size": 200,
            },
        )

    def test_provider_is_required(self) -> None:
        for provider in ("", "   ", None):
            with self.subTest(provider=provider):
                with self.assertRaisesRegex(
                    ProviderCapabilityError,
                    "provider is required",
                ):
                    _capabilities(provider=provider)

    def test_capabilities_must_be_frozenset(
        self,
    ) -> None:
        for capabilities in (
            set(),
            tuple(),
            list(),
            None,
        ):
            with self.subTest(
                capabilities=capabilities,
            ):
                with self.assertRaisesRegex(
                    ProviderCapabilityError,
                    "capabilities must be a frozenset",
                ):
                    _capabilities(
                        capabilities=capabilities,
                        supports_batch_listing=False,
                        max_batch_size=None,
                    )

    def test_invalid_capability_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            ProviderCapabilityError,
            "invalid provider capability",
        ):
            _capabilities(
                capabilities=frozenset(
                    {
                        "list_media",
                        "archive",
                    }
                )
            )

    def test_batch_flags_require_booleans(self) -> None:
        cases = (
            ("supports_batch_listing", 1),
            ("supports_batch_listing", "true"),
            ("supports_batch_listing", None),
            ("supports_batch_preview", 0),
            ("supports_batch_preview", "false"),
            ("supports_batch_preview", None),
        )

        for field_name, value in cases:
            with self.subTest(
                field_name=field_name,
                value=value,
            ):
                with self.assertRaisesRegex(
                    ProviderCapabilityError,
                    rf"{field_name} must be a boolean",
                ):
                    _capabilities(
                        **{field_name: value}
                    )

    def test_max_batch_size_is_validated(self) -> None:
        for value in (
            0,
            -1,
            True,
            1.5,
            "200",
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ProviderCapabilityError,
                    "max_batch_size must be a positive",
                ):
                    _capabilities(
                        max_batch_size=value,
                    )

    def test_max_batch_size_may_be_none(self) -> None:
        capabilities = _capabilities(
            supports_batch_listing=False,
            max_batch_size=None,
        )

        self.assertIsNone(
            capabilities.max_batch_size
        )

    def test_batch_listing_requires_list_capability(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ProviderCapabilityError,
            "batch listing requires the list_media",
        ):
            _capabilities(
                capabilities=frozenset(
                    {
                        ProviderCapability.PREVIEW_DELETE,
                    }
                )
            )

    def test_batch_preview_requires_preview_capability(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ProviderCapabilityError,
            "batch preview requires the preview_delete",
        ):
            _capabilities(
                capabilities=frozenset(
                    {
                        ProviderCapability.LIST_MEDIA,
                    }
                ),
                supports_batch_listing=False,
                supports_batch_preview=True,
            )

    def test_batch_size_requires_batch_support(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ProviderCapabilityError,
            "max_batch_size requires batch support",
        ):
            _capabilities(
                supports_batch_listing=False,
                supports_batch_preview=False,
                max_batch_size=200,
            )

    def test_empty_capability_set_is_supported(
        self,
    ) -> None:
        capabilities = _capabilities(
            capabilities=frozenset(),
            supports_batch_listing=False,
            supports_batch_preview=False,
            max_batch_size=None,
        )

        self.assertEqual(
            capabilities.capabilities,
            frozenset(),
        )


if __name__ == "__main__":
    unittest.main()
