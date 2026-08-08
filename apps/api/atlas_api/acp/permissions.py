"""Permission registration for Atlas and installable modules."""

from __future__ import annotations

from types import MappingProxyType
from typing import Iterable, Mapping

from atlas_api.acp.exceptions import (
    ACPValidationError,
    DuplicatePermissionError,
)
from atlas_api.acp.models import (
    PermissionDefinition,
    PermissionGroup,
)


class PermissionRegistry:
    """In-memory registry of concrete ACP permission definitions."""

    def __init__(self) -> None:
        self._permissions: dict[str, PermissionDefinition] = {}
        self._groups: dict[str, PermissionGroup] = {}

    @property
    def permissions(
        self,
    ) -> Mapping[str, PermissionDefinition]:
        return MappingProxyType(self._permissions)

    @property
    def groups(self) -> Mapping[str, PermissionGroup]:
        return MappingProxyType(self._groups)

    def register_group(
        self,
        group: PermissionGroup,
    ) -> PermissionGroup:
        existing = self._groups.get(group.namespace)
        if existing is not None and existing != group:
            raise ACPValidationError(
                "Permission namespace is already registered with "
                f"different metadata: {group.namespace}"
            )
        self._groups[group.namespace] = group
        return group

    def register(
        self,
        permission: PermissionDefinition,
    ) -> PermissionDefinition:
        if permission.identifier in self._permissions:
            raise DuplicatePermissionError(permission.identifier)

        group = self._groups.get(permission.namespace)
        if group is None:
            raise ACPValidationError(
                "Register the permission namespace before its "
                f"permissions: {permission.namespace}"
            )
        if group.module != permission.module:
            raise ACPValidationError(
                "Permission module must match its registered group."
            )

        self._permissions[permission.identifier] = permission
        return permission

    def register_many(
        self,
        permissions: Iterable[PermissionDefinition],
    ) -> tuple[PermissionDefinition, ...]:
        registered: list[PermissionDefinition] = []
        for permission in permissions:
            registered.append(self.register(permission))
        return tuple(registered)

    def get(
        self,
        identifier: str,
    ) -> PermissionDefinition | None:
        return self._permissions.get(identifier.strip().lower())

    def require(
        self,
        identifier: str,
    ) -> PermissionDefinition:
        normalized = identifier.strip().lower()
        permission = self._permissions.get(normalized)
        if permission is None:
            raise KeyError(
                f"Unknown Atlas permission: {normalized}"
            )
        return permission

    def list_permissions(
        self,
        namespace: str | None = None,
    ) -> tuple[PermissionDefinition, ...]:
        values = self._permissions.values()
        if namespace is not None:
            normalized = namespace.strip().lower()
            values = (
                permission
                for permission in values
                if permission.namespace == normalized
            )
        return tuple(
            sorted(values, key=lambda value: value.identifier)
        )

    def list_groups(self) -> tuple[PermissionGroup, ...]:
        return tuple(
            sorted(
                self._groups.values(),
                key=lambda value: value.namespace,
            )
        )
