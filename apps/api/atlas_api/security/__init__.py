"""Reusable security dependencies for the Atlas HTTP API."""

from atlas_api.security.dependencies import require_permission, require_role
from atlas_api.security.permissions import (
    build_authorization_subject,
    evaluate_permission,
    subject_has_role,
)

__all__ = [
    "build_authorization_subject",
    "evaluate_permission",
    "require_permission",
    "require_role",
    "subject_has_role",
]
