"""Immutable comparison contracts for Atlas Operations reports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .models import (
    OperationFinding,
    OperationsModelError,
    OperationsReport,
    OperationsSectionId,
)


class OperationsChangeType(str, Enum):
    """Canonical change types between Operations reports."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class OperationsFindingChange:
    """One normalized finding-level change between two reports."""

    section: OperationsSectionId | str
    change_type: OperationsChangeType | str
    before: OperationFinding | None = None
    after: OperationFinding | None = None

    def __post_init__(self) -> None:
        section = _normalize_section_id(
            self.section,
            "section",
        )
        change_type = _normalize_change_type(
            self.change_type,
            "change_type",
        )
        before = _optional_finding(
            self.before,
            "before",
        )
        after = _optional_finding(
            self.after,
            "after",
        )

        _validate_change_contract(
            change_type=change_type,
            before=before,
            after=after,
        )

        if (
            before is not None
            and after is not None
            and before.identifier != after.identifier
        ):
            raise OperationsModelError(
                "before and after findings must share an identifier",
            )

        object.__setattr__(
            self,
            "section",
            section,
        )
        object.__setattr__(
            self,
            "change_type",
            change_type,
        )
        object.__setattr__(
            self,
            "before",
            before,
        )
        object.__setattr__(
            self,
            "after",
            after,
        )

    @property
    def identifier(self) -> str:
        """Return the canonical changed finding identity."""

        finding = self.after or self.before

        if finding is None:
            raise OperationsModelError(
                "finding change has no finding identity",
            )

        return finding.identifier

    @property
    def name(self) -> str:
        """Return the most recent available finding name."""

        finding = self.after or self.before

        if finding is None:
            raise OperationsModelError(
                "finding change has no finding name",
            )

        return finding.name

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "OperationsFindingChange":
        """Build a normalized finding change from serialized data."""

        if not isinstance(payload, Mapping):
            raise OperationsModelError(
                "finding change payload must be an object",
            )

        before_payload = payload.get("before")
        after_payload = payload.get("after")

        before = _finding_from_payload(
            before_payload,
            "before",
        )
        after = _finding_from_payload(
            after_payload,
            "after",
        )

        return cls(
            section=payload.get("section"),
            change_type=payload.get("change_type"),
            before=before,
            after=after,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized finding-change contract."""

        return {
            "identifier": self.identifier,
            "name": self.name,
            "section": self.section.value,
            "change_type": self.change_type.value,
            "before": (
                self.before.to_dict()
                if self.before is not None
                else None
            ),
            "after": (
                self.after.to_dict()
                if self.after is not None
                else None
            ),
        }


def _normalize_change_type(
    value: object,
    field_name: str,
) -> OperationsChangeType:
    if isinstance(value, OperationsChangeType):
        return value

    if not isinstance(value, str):
        raise OperationsModelError(
            f"{field_name} must be OperationsChangeType or text",
        )

    normalized = (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    try:
        return OperationsChangeType(normalized)
    except ValueError as error:
        raise OperationsModelError(
            f"{field_name} is not supported: {value!r}",
        ) from error


def _normalize_section_id(
    value: object,
    field_name: str,
) -> OperationsSectionId:
    if isinstance(value, OperationsSectionId):
        return value

    if not isinstance(value, str):
        raise OperationsModelError(
            f"{field_name} must be OperationsSectionId or text",
        )

    normalized = (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    try:
        return OperationsSectionId(normalized)
    except ValueError as error:
        raise OperationsModelError(
            f"{field_name} is not a supported Operations section: "
            f"{value!r}",
        ) from error


def _optional_finding(
    value: object,
    field_name: str,
) -> OperationFinding | None:
    if value is None:
        return None

    if not isinstance(value, OperationFinding):
        raise OperationsModelError(
            f"{field_name} must be an OperationFinding or null",
        )

    return value


def _finding_from_payload(
    payload: object,
    field_name: str,
) -> OperationFinding | None:
    if payload is None:
        return None

    if not isinstance(payload, Mapping):
        raise OperationsModelError(
            f"{field_name} finding payload must be an object or null",
        )

    return OperationFinding.from_dict(payload)


def _validate_change_contract(
    *,
    change_type: OperationsChangeType,
    before: OperationFinding | None,
    after: OperationFinding | None,
) -> None:
    if change_type is OperationsChangeType.ADDED:
        if before is not None or after is None:
            raise OperationsModelError(
                "added changes require only an after finding",
            )
        return

    if change_type is OperationsChangeType.REMOVED:
        if before is None or after is not None:
            raise OperationsModelError(
                "removed changes require only a before finding",
            )
        return

    if before is None or after is None:
        raise OperationsModelError(
            f"{change_type.value} changes require before and after findings",
        )

    if (
        change_type is OperationsChangeType.CHANGED
        and before == after
    ):
        raise OperationsModelError(
            "changed findings must not be equal",
        )

    if (
        change_type is OperationsChangeType.UNCHANGED
        and before != after
    ):
        raise OperationsModelError(
            "unchanged findings must be equal",
        )


_SECTION_ORDER = {
    section_id: index
    for index, section_id in enumerate(
        OperationsSectionId,
    )
}

_CHANGE_ORDER = {
    OperationsChangeType.ADDED: 0,
    OperationsChangeType.REMOVED: 1,
    OperationsChangeType.CHANGED: 2,
    OperationsChangeType.UNCHANGED: 3,
}


@dataclass(frozen=True, slots=True)
class OperationsComparison:
    """Normalized comparison between two Operations reports."""

    previous: OperationsReport
    current: OperationsReport
    changes: tuple[OperationsFindingChange, ...] = ()

    def __post_init__(self) -> None:
        previous = _required_report(
            self.previous,
            "previous",
        )
        current = _required_report(
            self.current,
            "current",
        )
        changes = tuple(
            sorted(
                _normalize_changes(
                    self.changes,
                    "changes",
                ),
                key=lambda change: (
                    _SECTION_ORDER[change.section],
                    change.identifier,
                    _CHANGE_ORDER[change.change_type],
                ),
            )
        )

        identities = [
            (
                change.section,
                change.identifier,
            )
            for change in changes
        ]

        if len(identities) != len(set(identities)):
            raise OperationsModelError(
                "comparison changes must have unique identities",
            )

        object.__setattr__(
            self,
            "previous",
            previous,
        )
        object.__setattr__(
            self,
            "current",
            current,
        )
        object.__setattr__(
            self,
            "changes",
            changes,
        )

    @property
    def added_count(self) -> int:
        return self._change_count(
            OperationsChangeType.ADDED,
        )

    @property
    def removed_count(self) -> int:
        return self._change_count(
            OperationsChangeType.REMOVED,
        )

    @property
    def changed_count(self) -> int:
        return self._change_count(
            OperationsChangeType.CHANGED,
        )

    @property
    def unchanged_count(self) -> int:
        return self._change_count(
            OperationsChangeType.UNCHANGED,
        )

    @property
    def difference_count(self) -> int:
        """Return changes that represent an actual difference."""

        return (
            self.added_count
            + self.removed_count
            + self.changed_count
        )

    @property
    def status_changed(self) -> bool:
        return self.previous.status is not self.current.status

    @property
    def score_delta(self) -> int:
        return self.current.score - self.previous.score

    @property
    def attention_delta(self) -> int:
        return (
            len(self.current.attention_findings)
            - len(self.previous.attention_findings)
        )

    def _change_count(
        self,
        change_type: OperationsChangeType,
    ) -> int:
        return sum(
            change.change_type is change_type
            for change in self.changes
        )

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "OperationsComparison":
        """Build a normalized comparison from serialized data."""

        if not isinstance(payload, Mapping):
            raise OperationsModelError(
                "comparison payload must be an object",
            )

        previous_payload = payload.get("previous")
        current_payload = payload.get("current")
        raw_changes = payload.get("changes", ())

        if not isinstance(previous_payload, Mapping):
            raise OperationsModelError(
                "previous report payload must be an object",
            )

        if not isinstance(current_payload, Mapping):
            raise OperationsModelError(
                "current report payload must be an object",
            )

        if not isinstance(raw_changes, (list, tuple)):
            raise OperationsModelError(
                "comparison changes must be a list or tuple",
            )

        return cls(
            previous=OperationsReport.from_dict(
                previous_payload,
            ),
            current=OperationsReport.from_dict(
                current_payload,
            ),
            changes=tuple(
                OperationsFindingChange.from_dict(change)
                for change in raw_changes
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete comparison contract."""

        return {
            "previous": self.previous.to_dict(),
            "current": self.current.to_dict(),
            "summary": {
                "previous_status": self.previous.status.value,
                "current_status": self.current.status.value,
                "status_changed": self.status_changed,
                "previous_score": self.previous.score,
                "current_score": self.current.score,
                "score_delta": self.score_delta,
                "previous_attention_count": len(
                    self.previous.attention_findings
                ),
                "current_attention_count": len(
                    self.current.attention_findings
                ),
                "attention_delta": self.attention_delta,
                "change_count": len(self.changes),
                "difference_count": self.difference_count,
                "added_count": self.added_count,
                "removed_count": self.removed_count,
                "changed_count": self.changed_count,
                "unchanged_count": self.unchanged_count,
            },
            "changes": [
                change.to_dict()
                for change in self.changes
            ],
        }


def _required_report(
    value: object,
    field_name: str,
) -> OperationsReport:
    if not isinstance(value, OperationsReport):
        raise OperationsModelError(
            f"{field_name} must be an OperationsReport",
        )

    return value


def _normalize_changes(
    value: object,
    field_name: str,
) -> tuple[OperationsFindingChange, ...]:
    if not isinstance(value, (list, tuple)):
        raise OperationsModelError(
            f"{field_name} must be a list or tuple",
        )

    changes: list[OperationsFindingChange] = []

    for change in value:
        if not isinstance(change, OperationsFindingChange):
            raise OperationsModelError(
                f"{field_name} must contain "
                "OperationsFindingChange values",
            )

        changes.append(change)

    return tuple(changes)
