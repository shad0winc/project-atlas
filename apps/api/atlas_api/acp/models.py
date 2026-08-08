"""Immutable domain models for the Atlas Access Control Platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from atlas_api.acp.exceptions import ACPValidationError


def _required_text(value: object, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise ACPValidationError(f"{field_name} cannot be empty.")
    return normalized


def _identifier(value: object, field_name: str) -> str:
    normalized = _required_text(value, field_name).lower()
    allowed = set(
        "abcdefghijklmnopqrstuvwxyz0123456789._-*"
    )
    if any(character not in allowed for character in normalized):
        raise ACPValidationError(
            f"{field_name} contains unsupported characters."
        )
    return normalized


def _string_set(
    values: Iterable[object],
    field_name: str,
    *,
    identifiers: bool = False,
) -> frozenset[str]:
    normalizer = _identifier if identifiers else _required_text
    return frozenset(
        normalizer(value, field_name)
        for value in values
    )


def _utc_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            value = datetime.fromisoformat(text)
        except ValueError as error:
            raise ACPValidationError(
                "Timestamp must be valid ISO-8601."
            ) from error

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def _metadata(
    value: Mapping[str, Any] | None,
) -> Mapping[str, Any]:
    return MappingProxyType(dict(value or {}))


class Visibility(StrEnum):
    """Supported visibility modes for ACP-managed resources."""

    PUBLIC = "public"
    PRIVATE = "private"
    SHARED = "shared"


@dataclass(frozen=True, slots=True)
class PermissionDefinition:
    """One concrete permission exposed by Atlas or an Atlas module."""

    identifier: str
    display_name: str
    description: str
    namespace: str
    module: str = "atlas"
    dangerous: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier = _identifier(
            self.identifier,
            "Permission identifier",
        )
        if "*" in identifier:
            raise ACPValidationError(
                "Registered permissions must be concrete identifiers."
            )

        namespace = _identifier(
            self.namespace,
            "Permission namespace",
        )
        if not identifier.startswith(f"{namespace}."):
            raise ACPValidationError(
                "Permission identifier must begin with its namespace."
            )

        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "Display name"),
        )
        object.__setattr__(
            self,
            "description",
            _required_text(self.description, "Description"),
        )
        object.__setattr__(self, "namespace", namespace)
        object.__setattr__(
            self,
            "module",
            _identifier(self.module, "Module"),
        )
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "identifier": self.identifier,
            "display_name": self.display_name,
            "description": self.description,
            "namespace": self.namespace,
            "module": self.module,
            "dangerous": self.dangerous,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> PermissionDefinition:
        return cls(
            identifier=value["identifier"],
            display_name=value["display_name"],
            description=value["description"],
            namespace=value["namespace"],
            module=value.get("module", "atlas"),
            dangerous=bool(value.get("dangerous", False)),
            metadata=value.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class PermissionGroup:
    """Human-facing grouping for related permission definitions."""

    namespace: str
    display_name: str
    description: str
    module: str = "atlas"

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "namespace",
            _identifier(self.namespace, "Permission namespace"),
        )
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "Display name"),
        )
        object.__setattr__(
            self,
            "description",
            _required_text(self.description, "Description"),
        )
        object.__setattr__(
            self,
            "module",
            _identifier(self.module, "Module"),
        )

    def to_dict(self) -> dict[str, str]:
        return {
            "namespace": self.namespace,
            "display_name": self.display_name,
            "description": self.description,
            "module": self.module,
        }


@dataclass(frozen=True, slots=True)
class ACPRole:
    """A role that grants one or more permission patterns."""

    name: str
    display_name: str
    description: str
    permissions: frozenset[str] = frozenset()
    protected: bool = False
    assignable: bool = True
    system: bool = False
    created_at: datetime | str | None = None
    updated_at: datetime | str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        created_at = _utc_datetime(self.created_at)
        updated_at = _utc_datetime(self.updated_at or created_at)
        if updated_at < created_at:
            raise ACPValidationError(
                "Role updated_at cannot be earlier than created_at."
            )

        object.__setattr__(
            self,
            "name",
            _identifier(self.name, "Role name"),
        )
        object.__setattr__(
            self,
            "display_name",
            _required_text(self.display_name, "Display name"),
        )
        object.__setattr__(
            self,
            "description",
            _required_text(self.description, "Description"),
        )
        object.__setattr__(
            self,
            "permissions",
            _string_set(
                self.permissions,
                "Permission",
                identifiers=True,
            ),
        )
        object.__setattr__(self, "created_at", created_at)
        object.__setattr__(self, "updated_at", updated_at)
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata),
        )

        if self.protected and not self.system:
            raise ACPValidationError(
                "Protected roles must be system roles."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "permissions": sorted(self.permissions),
            "protected": self.protected,
            "assignable": self.assignable,
            "system": self.system,
            "created_at": _timestamp(self.created_at),
            "updated_at": _timestamp(self.updated_at),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> ACPRole:
        return cls(
            name=value["name"],
            display_name=value["display_name"],
            description=value["description"],
            permissions=frozenset(value.get("permissions", ())),
            protected=bool(value.get("protected", False)),
            assignable=bool(value.get("assignable", True)),
            system=bool(value.get("system", False)),
            created_at=value.get("created_at"),
            updated_at=value.get("updated_at"),
            metadata=value.get("metadata", {}),
        )


@dataclass(frozen=True, slots=True)
class OwnershipRecord:
    """Ownership and visibility metadata for one ACP resource."""

    resource_type: str
    resource_id: str
    owner_user_id: str
    visibility: Visibility | str = Visibility.PRIVATE
    shared_with: frozenset[str] = frozenset()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        try:
            visibility = Visibility(self.visibility)
        except ValueError as error:
            raise ACPValidationError(
                f"Unsupported visibility: {self.visibility}"
            ) from error

        shared_with = _string_set(
            self.shared_with,
            "Shared user identifier",
        )
        if visibility is not Visibility.SHARED and shared_with:
            raise ACPValidationError(
                "shared_with requires shared visibility."
            )

        object.__setattr__(
            self,
            "resource_type",
            _identifier(self.resource_type, "Resource type"),
        )
        object.__setattr__(
            self,
            "resource_id",
            _required_text(self.resource_id, "Resource identifier"),
        )
        object.__setattr__(
            self,
            "owner_user_id",
            _required_text(self.owner_user_id, "Owner user identifier"),
        )
        object.__setattr__(self, "visibility", visibility)
        object.__setattr__(self, "shared_with", shared_with)
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata),
        )

    def is_visible_to(self, user_id: str | None) -> bool:
        if self.visibility is Visibility.PUBLIC:
            return True
        if user_id is None:
            return False
        normalized_user_id = user_id.strip()
        return (
            normalized_user_id == self.owner_user_id
            or (
                self.visibility is Visibility.SHARED
                and normalized_user_id in self.shared_with
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "owner_user_id": self.owner_user_id,
            "visibility": self.visibility.value,
            "shared_with": sorted(self.shared_with),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class ResourceQuota:
    """Named integer limits assigned to one ACP subject."""

    subject_id: str
    limits: Mapping[str, int]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized_limits: dict[str, int] = {}
        for name, value in self.limits.items():
            key = _identifier(name, "Quota name")
            if isinstance(value, bool) or not isinstance(value, int):
                raise ACPValidationError(
                    f"Quota {key} must be an integer."
                )
            if value < 0:
                raise ACPValidationError(
                    f"Quota {key} cannot be negative."
                )
            normalized_limits[key] = value

        object.__setattr__(
            self,
            "subject_id",
            _required_text(self.subject_id, "Subject identifier"),
        )
        object.__setattr__(
            self,
            "limits",
            MappingProxyType(normalized_limits),
        )
        object.__setattr__(
            self,
            "metadata",
            _metadata(self.metadata),
        )

    def allows(self, resource: str, requested: int) -> bool:
        if isinstance(requested, bool) or requested < 0:
            raise ACPValidationError(
                "Requested quota usage must be a non-negative integer."
            )
        limit = self.limits.get(
            _identifier(resource, "Quota name")
        )
        return limit is not None and requested <= limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "subject_id": self.subject_id,
            "limits": dict(self.limits),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """An immutable ACP audit record."""

    event_type: str
    actor_user_id: str
    target_type: str
    target_id: str
    occurred_at: datetime | str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_type",
            _identifier(self.event_type, "Event type"),
        )
        object.__setattr__(
            self,
            "actor_user_id",
            _required_text(self.actor_user_id, "Actor user identifier"),
        )
        object.__setattr__(
            self,
            "target_type",
            _identifier(self.target_type, "Target type"),
        )
        object.__setattr__(
            self,
            "target_id",
            _required_text(self.target_id, "Target identifier"),
        )
        object.__setattr__(
            self,
            "occurred_at",
            _utc_datetime(self.occurred_at),
        )
        object.__setattr__(
            self,
            "details",
            _metadata(self.details),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "actor_user_id": self.actor_user_id,
            "target_type": self.target_type,
            "target_id": self.target_id,
            "occurred_at": _timestamp(self.occurred_at),
            "details": dict(self.details),
        }
