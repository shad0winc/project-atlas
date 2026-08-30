"""Persistent custom-role definitions for Project Atlas.

This module owns storage and validation only. Authorization composition and
HTTP mutation surfaces are intentionally layered on in later PR73 stages.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping


ROLE_SCHEMA_VERSION = 1
_ROLE_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_PERMISSION_COMPONENT_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class CustomRoleError(RuntimeError):
    """A custom-role definition or store operation is invalid."""


@dataclass(frozen=True, slots=True)
class CustomRoleDefinition:
    """One persisted Atlas custom role."""

    name: str
    display_name: str
    description: str
    permissions: frozenset[str]
    assignable: bool = True

    def __post_init__(self) -> None:
        normalized = normalize_custom_role_name(self.name)
        if normalized != self.name:
            raise CustomRoleError(
                "Custom role names must already be normalized lowercase values."
            )
        if not self.display_name.strip():
            raise CustomRoleError("Custom role display name cannot be empty.")
        if not self.description.strip():
            raise CustomRoleError("Custom role description cannot be empty.")
        if not self.permissions:
            raise CustomRoleError("Custom roles require at least one permission.")
        for permission in self.permissions:
            validate_permission_pattern(permission)

    def to_payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "permissions": sorted(self.permissions),
            "assignable": self.assignable,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "CustomRoleDefinition":
        required = {"name", "display_name", "description", "permissions", "assignable"}
        extra = set(payload) - required
        missing = required - set(payload)
        if extra or missing:
            raise CustomRoleError("Custom role payload fields are invalid.")

        permissions = payload["permissions"]
        if isinstance(permissions, str) or not isinstance(permissions, list):
            raise CustomRoleError("Custom role permissions must be a list.")

        assignable = payload["assignable"]
        if not isinstance(assignable, bool):
            raise CustomRoleError("Custom role assignable must be a boolean.")

        return cls(
            name=str(payload["name"]),
            display_name=str(payload["display_name"]),
            description=str(payload["description"]),
            permissions=frozenset(str(value) for value in permissions),
            assignable=assignable,
        )


def normalize_custom_role_name(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise CustomRoleError("Custom role name cannot be empty.")
    if not _ROLE_NAME_RE.fullmatch(normalized):
        raise CustomRoleError(
            "Custom role names may contain only lowercase letters, numbers, underscores, and hyphens."
        )
    return normalized


def validate_permission_pattern(value: str) -> str:
    permission = value.strip().lower()
    if not permission:
        raise CustomRoleError("Permission pattern cannot be empty.")
    if permission == "*":
        return permission
    components = permission.split(".")
    if len(components) < 2:
        raise CustomRoleError("Permissions must contain a namespace and action.")
    if components.count("*") > 1:
        raise CustomRoleError("Permission patterns may contain at most one wildcard component.")
    for component in components:
        if component == "*":
            continue
        if not component or not _PERMISSION_COMPONENT_RE.fullmatch(component):
            raise CustomRoleError("Permission components contain invalid characters.")
    return permission


class CustomRoleStore:
    """Atomic JSON-backed custom-role store."""

    def __init__(self, path: Path, *, reserved_names: Iterable[str] = ()) -> None:
        self.path = Path(path)
        self.reserved_names = frozenset(
            normalize_custom_role_name(name) for name in reserved_names
        )

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write({})

    def list_roles(self) -> tuple[CustomRoleDefinition, ...]:
        roles = self._read()
        return tuple(roles[name] for name in sorted(roles))

    def get(self, name: str) -> CustomRoleDefinition | None:
        return self._read().get(normalize_custom_role_name(name))

    def create(self, definition: CustomRoleDefinition) -> CustomRoleDefinition:
        roles = self._read()
        self._assert_available_name(definition.name, roles)
        roles[definition.name] = definition
        self._write(roles)
        return definition

    def update(
        self,
        name: str,
        *,
        display_name: str,
        description: str,
        permissions: Iterable[str],
        assignable: bool,
    ) -> CustomRoleDefinition:
        normalized = normalize_custom_role_name(name)
        roles = self._read()
        if normalized not in roles:
            raise CustomRoleError("Custom role not found.")
        definition = CustomRoleDefinition(
            name=normalized,
            display_name=display_name,
            description=description,
            permissions=frozenset(validate_permission_pattern(p) for p in permissions),
            assignable=assignable,
        )
        roles[normalized] = definition
        self._write(roles)
        return definition

    def delete(self, name: str, *, assigned_roles: Iterable[str] = ()) -> None:
        normalized = normalize_custom_role_name(name)
        roles = self._read()
        if normalized not in roles:
            raise CustomRoleError("Custom role not found.")
        assigned = {normalize_custom_role_name(value) for value in assigned_roles}
        if normalized in assigned:
            raise CustomRoleError("Custom role is assigned and cannot be deleted.")
        del roles[normalized]
        self._write(roles)

    def _assert_available_name(
        self,
        name: str,
        roles: Mapping[str, CustomRoleDefinition],
    ) -> None:
        normalized = normalize_custom_role_name(name)
        if normalized in self.reserved_names:
            raise CustomRoleError("Custom role name conflicts with a built-in role.")
        if normalized in roles:
            raise CustomRoleError("Custom role already exists.")

    def _read(self) -> dict[str, CustomRoleDefinition]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise CustomRoleError("Custom role store is unreadable.") from error
        if not isinstance(payload, dict) or set(payload) != {"schema_version", "roles"}:
            raise CustomRoleError("Custom role store schema is invalid.")
        if payload["schema_version"] != ROLE_SCHEMA_VERSION:
            raise CustomRoleError("Custom role store schema version is unsupported.")
        raw_roles = payload["roles"]
        if not isinstance(raw_roles, list):
            raise CustomRoleError("Custom role store roles must be a list.")
        roles: dict[str, CustomRoleDefinition] = {}
        for raw in raw_roles:
            if not isinstance(raw, dict):
                raise CustomRoleError("Custom role entry must be an object.")
            definition = CustomRoleDefinition.from_payload(raw)
            if definition.name in self.reserved_names:
                raise CustomRoleError("Custom role store contains a built-in role name.")
            if definition.name in roles:
                raise CustomRoleError("Custom role store contains duplicate role names.")
            roles[definition.name] = definition
        return roles

    def _write(self, roles: Mapping[str, CustomRoleDefinition]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": ROLE_SCHEMA_VERSION,
            "roles": [roles[name].to_payload() for name in sorted(roles)],
        }
        fd, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=self.path.parent,
            text=True,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o640)
            os.replace(temporary, self.path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise


def default_custom_role_store(*, reserved_names: Iterable[str] = ()) -> CustomRoleStore:
    path = Path(
        os.getenv(
            "ATLAS_CUSTOM_ROLES_PATH",
            "/mnt/storage/configs/atlas/identity/custom_roles/custom_roles.json",
        )
    ).expanduser().resolve()
    return CustomRoleStore(path, reserved_names=reserved_names)
