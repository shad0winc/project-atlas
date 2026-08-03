"""Base contracts for Project Atlas Operations collectors."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math
from typing import Any

from atlas.operations.models import (
    OperationsSection,
    OperationsSectionId,
)


class OperationsCollectorError(RuntimeError):
    """Raised when an Operations collector cannot complete."""


class OperationsCollectorContractError(OperationsCollectorError):
    """Raised when a collector returns an invalid domain contract."""


class OperationsCollectorTimeoutError(OperationsCollectorError):
    """Raised when a collector exceeds its configured timeout."""


@dataclass(frozen=True, slots=True)
class OperationsCollector(ABC):
    """Provider-neutral base contract for Operations collectors."""

    section_id: OperationsSectionId | str
    name: str
    timeout_seconds: float = 10.0
    description: str | None = None

    def __post_init__(self) -> None:
        section_id = _normalize_section_id(self.section_id)
        name = _required_text(self.name, "name")
        timeout_seconds = _positive_number(
            self.timeout_seconds,
            "timeout_seconds",
        )
        description = _optional_text(
            self.description,
            "description",
        )

        object.__setattr__(self, "section_id", section_id)
        object.__setattr__(self, "name", name)
        object.__setattr__(
            self,
            "timeout_seconds",
            timeout_seconds,
        )
        object.__setattr__(
            self,
            "description",
            description,
        )

    @abstractmethod
    def collect(self) -> OperationsSection:
        """Collect and return one normalized Operations section."""

    def collect_checked(self) -> OperationsSection:
        """Collect and enforce the collector output contract."""

        try:
            section = self.collect()
        except OperationsCollectorError:
            raise
        except Exception as exc:
            raise OperationsCollectorError(
                f"{self.section_id.value} collector failed: {exc}",
            ) from exc

        if not isinstance(section, OperationsSection):
            raise OperationsCollectorContractError(
                "collector must return an OperationsSection",
            )

        if section.identifier is not self.section_id:
            raise OperationsCollectorContractError(
                "collector returned the wrong section identity: "
                f"expected {self.section_id.value}, "
                f"found {section.identifier.value}",
            )

        return section

    def to_dict(self) -> dict[str, Any]:
        """Serialize deterministic collector metadata."""

        return {
            "section_id": self.section_id.value,
            "name": self.name,
            "description": self.description,
            "timeout_seconds": self.timeout_seconds,
        }


def _normalize_section_id(
    value: object,
) -> OperationsSectionId:
    if isinstance(value, OperationsSectionId):
        return value

    if not isinstance(value, str):
        raise OperationsCollectorContractError(
            "section_id must be OperationsSectionId or text",
        )

    normalized = (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    try:
        return OperationsSectionId(normalized)
    except ValueError as exc:
        raise OperationsCollectorContractError(
            f"unsupported Operations section: {value!r}",
        ) from exc


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise OperationsCollectorContractError(
            f"{field_name} must be text",
        )

    normalized = value.strip()

    if not normalized:
        raise OperationsCollectorContractError(
            f"{field_name} is required",
        )

    return normalized


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_text(value, field_name)


def _positive_number(
    value: object,
    field_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OperationsCollectorContractError(
            f"{field_name} must be a number",
        )

    normalized = float(value)

    if not math.isfinite(normalized) or normalized <= 0:
        raise OperationsCollectorContractError(
            f"{field_name} must be finite and greater than zero",
        )

    return normalized
