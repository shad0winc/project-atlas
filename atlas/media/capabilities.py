"""Provider capability contracts for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ProviderCapabilityError(ValueError):
    """Raised when a provider capability contract is invalid."""


class ProviderCapability(str, Enum):
    """Operations that a media provider may support."""

    LIST_MEDIA = "list_media"
    PREVIEW_DELETE = "preview_delete"
    DELETE = "delete"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Immutable description of supported provider behavior."""

    provider: str
    capabilities: frozenset[ProviderCapability]
    supports_batch_listing: bool = False
    supports_batch_preview: bool = False
    max_batch_size: int | None = None

    def __post_init__(self) -> None:
        """Normalize and validate the capability contract."""

        provider = _required_text(
            self.provider,
            "provider",
        ).lower()

        if not isinstance(self.capabilities, frozenset):
            raise ProviderCapabilityError(
                "capabilities must be a frozenset"
            )

        normalized_capabilities: set[ProviderCapability] = set()

        for capability in self.capabilities:
            try:
                normalized = (
                    capability
                    if isinstance(
                        capability,
                        ProviderCapability,
                    )
                    else ProviderCapability(capability)
                )
            except (TypeError, ValueError) as exc:
                raise ProviderCapabilityError(
                    "invalid provider capability: "
                    f"{capability}"
                ) from exc

            normalized_capabilities.add(normalized)

        if not isinstance(
            self.supports_batch_listing,
            bool,
        ):
            raise ProviderCapabilityError(
                "supports_batch_listing must be a boolean"
            )

        if not isinstance(
            self.supports_batch_preview,
            bool,
        ):
            raise ProviderCapabilityError(
                "supports_batch_preview must be a boolean"
            )

        max_batch_size = self.max_batch_size

        if max_batch_size is not None:
            if (
                isinstance(max_batch_size, bool)
                or not isinstance(max_batch_size, int)
                or max_batch_size <= 0
            ):
                raise ProviderCapabilityError(
                    "max_batch_size must be a positive "
                    "integer or None"
                )

        normalized = frozenset(normalized_capabilities)

        if (
            self.supports_batch_listing
            and ProviderCapability.LIST_MEDIA
            not in normalized
        ):
            raise ProviderCapabilityError(
                "batch listing requires the list_media "
                "capability"
            )

        if (
            self.supports_batch_preview
            and ProviderCapability.PREVIEW_DELETE
            not in normalized
        ):
            raise ProviderCapabilityError(
                "batch preview requires the preview_delete "
                "capability"
            )

        if (
            max_batch_size is not None
            and not self.supports_batch_listing
            and not self.supports_batch_preview
        ):
            raise ProviderCapabilityError(
                "max_batch_size requires batch support"
            )

        object.__setattr__(
            self,
            "provider",
            provider,
        )
        object.__setattr__(
            self,
            "capabilities",
            normalized,
        )

    def supports(
        self,
        capability: ProviderCapability | str,
    ) -> bool:
        """Return whether the provider supports a capability."""

        try:
            normalized = (
                capability
                if isinstance(
                    capability,
                    ProviderCapability,
                )
                else ProviderCapability(capability)
            )
        except (TypeError, ValueError) as exc:
            raise ProviderCapabilityError(
                "invalid provider capability: "
                f"{capability}"
            ) from exc

        return normalized in self.capabilities

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation."""

        return {
            "provider": self.provider,
            "capabilities": sorted(
                capability.value
                for capability in self.capabilities
            ),
            "supports_batch_listing": (
                self.supports_batch_listing
            ),
            "supports_batch_preview": (
                self.supports_batch_preview
            ),
            "max_batch_size": self.max_batch_size,
        }


def _required_text(
    value: object,
    field_name: str,
) -> str:
    """Return a stripped, non-empty string."""

    if not isinstance(value, str) or not value.strip():
        raise ProviderCapabilityError(
            f"{field_name} is required"
        )

    return value.strip()
