"""Administrator role and permission-management routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from atlas.custom_roles import default_custom_role_store
from atlas.user_profiles import VALID_ROLES
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.authorization import BUILT_IN_ROLES
from atlas_api.dependencies import get_identity_writer_client
from atlas_api.security.dependencies import require_permission
from atlas_api.services.identity_writer import IdentityWriterClient, IdentityWriterError

router = APIRouter(prefix="/admin/roles", tags=["admin-roles"])

require_roles_read = require_permission("roles.read")
require_roles_assign = require_permission("roles.assign")
require_roles_create = require_permission("roles.create")
require_roles_update = require_permission("roles.update")
require_roles_delete = require_permission("roles.delete")


class AdminRoleCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    display_name: str
    description: str = ""
    permissions: list[str]
    assignable: bool = True


class AdminRoleUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None
    assignable: bool | None = None


def _role_payload(role: Any, *, source: str) -> dict[str, Any]:
    return {
        "name": role.name,
        "display_name": role.display_name,
        "description": role.description,
        "permissions": sorted(role.permissions),
        "protected": bool(getattr(role, "protected", False)),
        "assignable": role.assignable,
        "source": source,
    }


def _permission_catalog() -> list[str]:
    # Canonical currently-supported permission patterns are derived from the
    # built-in catalog. Custom roles may select these; the Portal never invents
    # arbitrary strings. Owner's unrestricted '*' is intentionally excluded.
    return sorted({
        permission
        for role in BUILT_IN_ROLES.values()
        for permission in role.permissions
        if permission != "*"
    })


@router.get("")
def list_admin_roles(
    _user: AuthenticatedUser = Depends(require_roles_read),
) -> dict[str, Any]:
    custom = default_custom_role_store(reserved_names=VALID_ROLES)
    return {
        "roles": [
            *[_role_payload(role, source="built_in") for role in BUILT_IN_ROLES.values()],
            *[_role_payload(role, source="custom") for role in custom.list_roles()],
        ],
        "permissions": _permission_catalog(),
    }


@router.get("/assignable")
def list_assignable_roles(
    _user: AuthenticatedUser = Depends(require_roles_assign),
) -> dict[str, Any]:
    custom = default_custom_role_store(reserved_names=VALID_ROLES)
    roles = [*BUILT_IN_ROLES.values(), *custom.list_roles()]
    return {
        "roles": [
            {"name": role.name, "display_name": role.display_name, "assignable": role.assignable}
            for role in roles
            if role.assignable
        ]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_admin_role(
    request: AdminRoleCreateRequest,
    _user: AuthenticatedUser = Depends(require_roles_create),
    writer: IdentityWriterClient = Depends(get_identity_writer_client),
) -> dict[str, Any]:
    try:
        return writer.create_custom_role(request.model_dump())
    except IdentityWriterError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.patch("/{role_name}")
def update_admin_role(
    role_name: str,
    request: AdminRoleUpdateRequest,
    _user: AuthenticatedUser = Depends(require_roles_update),
    writer: IdentityWriterClient = Depends(get_identity_writer_client),
) -> dict[str, Any]:
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one role update field is required.")
    try:
        return writer.update_custom_role(role_name, updates)
    except IdentityWriterError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error


@router.delete("/{role_name}")
def delete_admin_role(
    role_name: str,
    _user: AuthenticatedUser = Depends(require_roles_delete),
    writer: IdentityWriterClient = Depends(get_identity_writer_client),
) -> dict[str, Any]:
    try:
        return writer.delete_custom_role(role_name)
    except IdentityWriterError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
