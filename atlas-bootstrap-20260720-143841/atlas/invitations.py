"""Secure invitation lifecycle storage for Atlas identities.

Invitation tokens are returned only when issued. Durable records contain a
SHA-256 digest, never the plaintext token.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from atlas.atomic import write_json_atomic
from atlas.identity import IdentityPaths, default_identity_paths
from atlas.time import format_timestamp, parse_timestamp, utc_now
from atlas.user_profiles import normalize_email, normalize_role

SCHEMA_VERSION = 1
REGISTRY_SCHEMA_VERSION = 1
TOKEN_PREFIX = "atlas_inv_"
VALID_STATUSES = frozenset({"pending", "completed", "revoked", "expired"})
_ARCHIVE_STATUSES = frozenset({"completed", "revoked", "expired"})


class InvitationError(ValueError):
    """Raised when an invitation operation cannot be completed."""


@dataclass(frozen=True)
class InvitationIssue:
    """One-time result returned when an invitation is created."""

    invitation: dict[str, Any]
    token: str


@dataclass(frozen=True)
class InvitationStore:
    """Durable invitation store backed by the Atlas identity directory."""

    paths: IdentityPaths
    clock: Callable[[], datetime] = utc_now

    def initialize(self) -> None:
        self.paths.initialize()
        if not self.paths.invitation_registry.exists():
            write_json_atomic(
                self.paths.invitation_registry,
                {"schema_version": REGISTRY_SCHEMA_VERSION, "invitations": {}},
            )

    def create(
        self,
        *,
        email: str | None = None,
        role: str = "user",
        created_by: str | None = None,
        expires_in: timedelta = timedelta(days=7),
    ) -> InvitationIssue:
        """Create an invitation and return its plaintext token exactly once."""
        if expires_in <= timedelta(0):
            raise InvitationError("invitation expiration must be greater than zero")

        self.initialize()
        now = _require_aware(self.clock())
        token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        invite_id = f"inv_{uuid.uuid4().hex}"
        record = validate_invitation(
            {
                "schema_version": SCHEMA_VERSION,
                "invite_id": invite_id,
                "token_hash": hash_token(token),
                "email": normalize_email(email),
                "role": normalize_role(role),
                "created_by": _optional_identifier(created_by),
                "created_at": format_timestamp(now),
                "expires_at": format_timestamp(now + expires_in),
                "status": "pending",
                "completed_at": None,
                "completed_by": None,
                "revoked_at": None,
                "revoked_by": None,
            }
        )

        registry = self._load_registry()
        record_path = self._record_path(invite_id, "pending")
        write_json_atomic(record_path, record)
        registry["invitations"][invite_id] = self._registry_entry(record, record_path)
        try:
            write_json_atomic(self.paths.invitation_registry, registry)
        except Exception:
            record_path.unlink(missing_ok=True)
            raise
        return InvitationIssue(record, token)

    def get(self, invite_id: str) -> dict[str, Any]:
        self.initialize()
        registry = self._load_registry()
        entry = registry["invitations"].get(invite_id)
        if not isinstance(entry, dict):
            raise InvitationError(f"invitation not found: {invite_id}")
        path = self._safe_registry_path(entry.get("path"), invite_id)
        return validate_invitation(_read_json(path))

    def verify_token(self, token: str) -> dict[str, Any]:
        """Return a usable pending invitation matching a plaintext token."""
        digest = hash_token(token)
        now = _require_aware(self.clock())
        for record in self.list(status="pending"):
            if secrets.compare_digest(record["token_hash"], digest):
                if _expiration(record) <= now:
                    self._archive(record["invite_id"], "expired")
                    raise InvitationError("invitation has expired")
                return record
        raise InvitationError("invalid invitation token")

    def revoke(self, invite_id: str, *, revoked_by: str | None = None) -> dict[str, Any]:
        record = self.get(invite_id)
        if record["status"] != "pending":
            raise InvitationError(f"invitation is not pending: {invite_id}")
        return self._archive(invite_id, "revoked", actor=revoked_by)

    def complete(
        self,
        invite_id: str,
        *,
        completed_by: str,
    ) -> dict[str, Any]:
        record = self.get(invite_id)
        if record["status"] != "pending":
            raise InvitationError(f"invitation is not pending: {invite_id}")
        if _expiration(record) <= _require_aware(self.clock()):
            self._archive(invite_id, "expired")
            raise InvitationError("invitation has expired")
        return self._archive(invite_id, "completed", actor=completed_by)

    def list(self, *, status: str | None = None) -> list[dict[str, Any]]:
        self.initialize()
        if status is not None and status not in VALID_STATUSES:
            raise InvitationError("invalid invitation status")
        registry = self._load_registry()
        records = []
        for invite_id, entry in registry["invitations"].items():
            if status is not None and entry["status"] != status:
                continue
            records.append(self.get(invite_id))
        return sorted(records, key=lambda item: (item["created_at"], item["invite_id"]))

    def cleanup_expired(self) -> list[str]:
        """Archive all expired pending invitations and return their IDs."""
        now = _require_aware(self.clock())
        expired = [
            record["invite_id"]
            for record in self.list(status="pending")
            if _expiration(record) <= now
        ]
        for invite_id in expired:
            self._archive(invite_id, "expired")
        return expired

    def verify(self) -> list[str]:
        """Return storage-consistency errors without mutating records."""
        self.initialize()
        errors: list[str] = []
        try:
            registry = self._load_registry()
        except (InvitationError, OSError, json.JSONDecodeError) as exc:
            return [str(exc)]

        seen_hashes: set[str] = set()
        referenced_paths: set[Path] = set()
        for invite_id, entry in registry["invitations"].items():
            try:
                path = self._safe_registry_path(entry["path"], invite_id)
                referenced_paths.add(path)
                record = validate_invitation(_read_json(path))
                if record["invite_id"] != invite_id:
                    errors.append(f"{invite_id}: record ID does not match registry")
                if record["status"] != entry["status"]:
                    errors.append(f"{invite_id}: record status does not match registry")
                if record["token_hash"] in seen_hashes:
                    errors.append(f"{invite_id}: duplicate token hash")
                seen_hashes.add(record["token_hash"])
            except (KeyError, InvitationError, OSError, json.JSONDecodeError) as exc:
                errors.append(f"{invite_id}: {exc}")

        for directory in (
            self.paths.active_invitations,
            self.paths.completed_invitations,
            self.paths.revoked_invitations,
        ):
            for path in directory.glob("inv_*.json"):
                if path.resolve() not in referenced_paths:
                    errors.append(f"unregistered invitation record: {path}")
        return errors

    def _archive(
        self,
        invite_id: str,
        status: str,
        *,
        actor: str | None = None,
    ) -> dict[str, Any]:
        if status not in _ARCHIVE_STATUSES:
            raise InvitationError(f"invalid archive status: {status}")
        self.initialize()
        registry = self._load_registry()
        entry = registry["invitations"].get(invite_id)
        if not isinstance(entry, dict) or entry.get("status") != "pending":
            raise InvitationError(f"pending invitation not found: {invite_id}")
        source = self._safe_registry_path(entry["path"], invite_id)
        record = validate_invitation(_read_json(source))
        timestamp = format_timestamp(_require_aware(self.clock()))
        record["status"] = status
        if status == "completed":
            record["completed_at"] = timestamp
            record["completed_by"] = _required_identifier(actor, "completed_by")
        elif status == "revoked":
            record["revoked_at"] = timestamp
            record["revoked_by"] = _optional_identifier(actor)
        else:
            record["revoked_at"] = timestamp
            record["revoked_by"] = None

        record = validate_invitation(record)
        destination = self._record_path(invite_id, status)
        write_json_atomic(destination, record)
        entry.update(self._registry_entry(record, destination))
        try:
            write_json_atomic(self.paths.invitation_registry, registry)
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        source.unlink(missing_ok=True)
        return record

    def _load_registry(self) -> dict[str, Any]:
        data = _read_json(self.paths.invitation_registry)
        if data.get("schema_version") != REGISTRY_SCHEMA_VERSION:
            raise InvitationError("unsupported invitation registry schema")
        invitations = data.get("invitations")
        if not isinstance(invitations, dict):
            raise InvitationError("invitation registry must contain an invitations object")
        for invite_id, entry in invitations.items():
            if not isinstance(entry, dict):
                raise InvitationError(f"invalid invitation registry entry: {invite_id}")
            if entry.get("status") not in VALID_STATUSES:
                raise InvitationError(f"invalid invitation registry status: {invite_id}")
            if not isinstance(entry.get("path"), str):
                raise InvitationError(f"invalid invitation registry path: {invite_id}")
        return data

    def _record_path(self, invite_id: str, status: str) -> Path:
        if status == "pending":
            directory = self.paths.active_invitations
        elif status == "completed":
            directory = self.paths.completed_invitations
        else:
            directory = self.paths.revoked_invitations
        return directory / f"{invite_id}.json"

    def _safe_registry_path(self, value: object, invite_id: str) -> Path:
        if not isinstance(value, str):
            raise InvitationError(f"invalid invitation path: {invite_id}")
        path = (self.paths.invitations_root / value).resolve()
        try:
            path.relative_to(self.paths.invitations_root.resolve())
        except ValueError as exc:
            raise InvitationError(f"invitation path escapes identity directory: {invite_id}") from exc
        return path

    def _registry_entry(self, record: Mapping[str, Any], path: Path) -> dict[str, str]:
        return {
            "status": str(record["status"]),
            "path": path.relative_to(self.paths.invitations_root).as_posix(),
        }


def hash_token(token: str) -> str:
    if not isinstance(token, str) or not token.startswith(TOKEN_PREFIX):
        raise InvitationError("invalid invitation token")
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def validate_invitation(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "invite_id", "token_hash", "email", "role",
        "created_by", "created_at", "expires_at", "status", "completed_at",
        "completed_by", "revoked_at", "revoked_by",
    }
    missing = required - set(value)
    if missing:
        raise InvitationError("invitation is missing fields: " + ", ".join(sorted(missing)))
    if value["schema_version"] != SCHEMA_VERSION:
        raise InvitationError("unsupported invitation schema")
    invite_id = str(value["invite_id"])
    if not invite_id.startswith("inv_") or len(invite_id) != 36:
        raise InvitationError("invalid invitation ID")
    token_hash = str(value["token_hash"])
    if len(token_hash) != 64 or any(character not in "0123456789abcdef" for character in token_hash):
        raise InvitationError("invalid invitation token hash")
    status = str(value["status"])
    if status not in VALID_STATUSES:
        raise InvitationError("invalid invitation status")

    created_at = _required_timestamp(value["created_at"], "created_at")
    expires_at = _required_timestamp(value["expires_at"], "expires_at")
    if expires_at <= created_at:
        raise InvitationError("invitation expiration must follow creation")

    normalized = dict(value)
    normalized["invite_id"] = invite_id
    normalized["token_hash"] = token_hash
    normalized["email"] = normalize_email(value["email"])
    normalized["role"] = normalize_role(str(value["role"]))
    normalized["created_by"] = _optional_identifier(value["created_by"])
    normalized["status"] = status
    normalized["completed_at"] = _optional_timestamp(value["completed_at"], "completed_at")
    normalized["completed_by"] = _optional_identifier(value["completed_by"])
    normalized["revoked_at"] = _optional_timestamp(value["revoked_at"], "revoked_at")
    normalized["revoked_by"] = _optional_identifier(value["revoked_by"])

    if status == "pending" and any(
        normalized[field] is not None
        for field in ("completed_at", "completed_by", "revoked_at", "revoked_by")
    ):
        raise InvitationError("pending invitation cannot contain lifecycle completion fields")
    if status == "completed" and (
        normalized["completed_at"] is None or normalized["completed_by"] is None
    ):
        raise InvitationError("completed invitation requires completion metadata")
    if status in {"revoked", "expired"} and normalized["revoked_at"] is None:
        raise InvitationError(f"{status} invitation requires archive timestamp")
    return normalized


def default_store() -> InvitationStore:
    return InvitationStore(default_identity_paths())


def _expiration(record: Mapping[str, Any]) -> datetime:
    return _required_timestamp(record["expires_at"], "expires_at")


def _required_timestamp(value: object, field: str) -> datetime:
    parsed = parse_timestamp(str(value)) if value is not None else None
    if parsed is None:
        raise InvitationError(f"invalid {field}")
    return parsed


def _optional_timestamp(value: object, field: str) -> str | None:
    if value is None:
        return None
    parsed = _required_timestamp(value, field)
    return format_timestamp(parsed)


def _required_identifier(value: object, field: str) -> str:
    normalized = _optional_identifier(value)
    if normalized is None:
        raise InvitationError(f"{field} is required")
    return normalized


def _optional_identifier(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    if len(normalized) > 128:
        raise InvitationError("identity reference is too long")
    return normalized


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise InvitationError("identity clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise InvitationError(f"missing invitation data file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise InvitationError(f"invalid invitation JSON file: {path}") from exc
    if not isinstance(value, dict):
        raise InvitationError(f"invitation JSON root must be an object: {path}")
    return value
