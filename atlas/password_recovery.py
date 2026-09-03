"""Durable single-use password recovery state for Atlas identities."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from atlas.identity import IdentityPaths, default_identity_paths
from atlas.time import format_timestamp, parse_timestamp, utc_now

SCHEMA_VERSION = 1
REGISTRY_SCHEMA_VERSION = 1
TOKEN_PREFIX = "atlas_reset_"
PASSWORD_RECOVERY_FILE_MODE = 0o640
VALID_STATUSES = frozenset({"pending", "completed", "revoked", "expired"})
_ARCHIVE_STATUSES = frozenset({"completed", "revoked", "expired"})


def _write_password_recovery_json_atomic(
    path: Path,
    value: Any,
) -> None:
    """Write password-recovery JSON atomically with private group-readable mode."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    content = (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as stream:
            os.fchmod(
                stream.fileno(),
                PASSWORD_RECOVERY_FILE_MODE,
            )
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        os.replace(
            temporary_path,
            path,
        )
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


class PasswordRecoveryError(ValueError):
    """Raised when password recovery state cannot be used safely."""


@dataclass(frozen=True)
class PasswordRecoveryIssue:
    """One-time recovery issue result containing the plaintext token."""

    recovery: dict[str, Any]
    token: str


@dataclass(frozen=True)
class PasswordRecoveryStore:
    """Durable password-recovery store under the Atlas identity root."""

    paths: IdentityPaths
    clock: Callable[[], datetime] = utc_now

    def initialize(self) -> None:
        self.paths.initialize()
        if not self.paths.password_recovery_registry.exists():
            _write_password_recovery_json_atomic(
                self.paths.password_recovery_registry,
                {
                    "schema_version": REGISTRY_SCHEMA_VERSION,
                    "recoveries": {},
                },
            )

    def create(
        self,
        *,
        user_id: str,
        expires_in: timedelta = timedelta(minutes=60),
    ) -> PasswordRecoveryIssue:
        if expires_in <= timedelta(0):
            raise PasswordRecoveryError(
                "password recovery expiration must be greater than zero"
            )

        normalized_user_id = _required_identifier(user_id, "user_id")
        self.initialize()
        self.revoke_active_for_user(normalized_user_id)

        now = _require_aware(self.clock())
        token = TOKEN_PREFIX + secrets.token_urlsafe(32)
        recovery_id = f"pwd_{uuid.uuid4().hex}"

        record = validate_recovery(
            {
                "schema_version": SCHEMA_VERSION,
                "recovery_id": recovery_id,
                "token_hash": hash_token(token),
                "user_id": normalized_user_id,
                "created_at": format_timestamp(now),
                "expires_at": format_timestamp(now + expires_in),
                "status": "pending",
                "completed_at": None,
                "revoked_at": None,
            }
        )

        registry = self._load_registry()
        path = self._record_path(recovery_id, "pending")
        _write_password_recovery_json_atomic(path, record)
        registry["recoveries"][recovery_id] = self._registry_entry(
            record,
            path,
        )

        try:
            _write_password_recovery_json_atomic(
                self.paths.password_recovery_registry,
                registry,
            )
        except Exception:
            path.unlink(missing_ok=True)
            raise

        return PasswordRecoveryIssue(record, token)

    def verify_token(self, token: str) -> dict[str, Any]:
        digest = hash_token(token)
        now = _require_aware(self.clock())

        for record in self.list(status="pending"):
            if secrets.compare_digest(record["token_hash"], digest):
                if _expiration(record) <= now:
                    self._archive(record["recovery_id"], "expired")
                    raise PasswordRecoveryError(
                        "password recovery token has expired"
                    )
                return record

        raise PasswordRecoveryError(
            "invalid password recovery token"
        )

    def complete(self, recovery_id: str) -> dict[str, Any]:
        return self._archive(recovery_id, "completed")

    def revoke(self, recovery_id: str) -> dict[str, Any]:
        return self._archive(recovery_id, "revoked")

    def revoke_active_for_user(self, user_id: str) -> list[str]:
        normalized_user_id = _required_identifier(user_id, "user_id")
        revoked: list[str] = []

        for record in self.list(status="pending"):
            if record["user_id"] == normalized_user_id:
                self._archive(record["recovery_id"], "revoked")
                revoked.append(record["recovery_id"])

        return revoked

    def list(
        self,
        *,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        if status is not None and status not in VALID_STATUSES:
            raise PasswordRecoveryError(
                "invalid password recovery status"
            )

        registry = self._load_registry()
        records: list[dict[str, Any]] = []

        for recovery_id, entry in registry["recoveries"].items():
            if status is not None and entry["status"] != status:
                continue
            records.append(self.get(recovery_id))

        return sorted(
            records,
            key=lambda item: (
                item["created_at"],
                item["recovery_id"],
            ),
        )

    def get(self, recovery_id: str) -> dict[str, Any]:
        registry = self._load_registry()
        entry = registry["recoveries"].get(recovery_id)

        if not isinstance(entry, dict):
            raise PasswordRecoveryError(
                f"password recovery not found: {recovery_id}"
            )

        path = self._safe_registry_path(
            entry.get("path"),
            recovery_id,
        )
        return validate_recovery(_read_json(path))

    def _archive(
        self,
        recovery_id: str,
        status: str,
    ) -> dict[str, Any]:
        if status not in _ARCHIVE_STATUSES:
            raise PasswordRecoveryError(
                f"invalid password recovery archive status: {status}"
            )

        self.initialize()
        registry = self._load_registry()
        entry = registry["recoveries"].get(recovery_id)

        if (
            not isinstance(entry, dict)
            or entry.get("status") != "pending"
        ):
            raise PasswordRecoveryError(
                f"pending password recovery not found: {recovery_id}"
            )

        source = self._safe_registry_path(
            entry["path"],
            recovery_id,
        )
        record = validate_recovery(_read_json(source))
        timestamp = format_timestamp(
            _require_aware(self.clock())
        )
        record["status"] = status

        if status == "completed":
            record["completed_at"] = timestamp
        else:
            record["revoked_at"] = timestamp

        record = validate_recovery(record)
        destination = self._record_path(
            recovery_id,
            status,
        )

        _write_password_recovery_json_atomic(destination, record)
        source.unlink(missing_ok=True)

        registry["recoveries"][recovery_id] = (
            self._registry_entry(record, destination)
        )
        _write_password_recovery_json_atomic(
            self.paths.password_recovery_registry,
            registry,
        )

        return record

    def _load_registry(self) -> dict[str, Any]:
        self.initialize()
        value = _read_json(
            self.paths.password_recovery_registry
        )

        if value.get("schema_version") != REGISTRY_SCHEMA_VERSION:
            raise PasswordRecoveryError(
                "unsupported password recovery registry schema"
            )

        recoveries = value.get("recoveries")
        if not isinstance(recoveries, dict):
            raise PasswordRecoveryError(
                "invalid password recovery registry"
            )

        return value

    def _record_path(
        self,
        recovery_id: str,
        status: str,
    ) -> Path:
        if status == "pending":
            directory = self.paths.active_password_recoveries
        elif status == "completed":
            directory = self.paths.completed_password_recoveries
        else:
            directory = self.paths.revoked_password_recoveries

        return directory / f"{recovery_id}.json"

    def _safe_registry_path(
        self,
        value: object,
        recovery_id: str,
    ) -> Path:
        if not isinstance(value, str):
            raise PasswordRecoveryError(
                f"invalid password recovery path: {recovery_id}"
            )

        path = (
            self.paths.password_recovery_root / value
        ).resolve()

        try:
            path.relative_to(
                self.paths.password_recovery_root.resolve()
            )
        except ValueError as exc:
            raise PasswordRecoveryError(
                "password recovery path escapes identity directory: "
                f"{recovery_id}"
            ) from exc

        return path

    def _registry_entry(
        self,
        record: Mapping[str, Any],
        path: Path,
    ) -> dict[str, str]:
        return {
            "status": str(record["status"]),
            "path": path.relative_to(
                self.paths.password_recovery_root
            ).as_posix(),
        }


def hash_token(token: str) -> str:
    if (
        not isinstance(token, str)
        or not token.startswith(TOKEN_PREFIX)
    ):
        raise PasswordRecoveryError(
            "invalid password recovery token"
        )

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def validate_recovery(
    value: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "schema_version",
        "recovery_id",
        "token_hash",
        "user_id",
        "created_at",
        "expires_at",
        "status",
        "completed_at",
        "revoked_at",
    }

    missing = required - set(value)
    if missing:
        raise PasswordRecoveryError(
            "password recovery is missing fields: "
            + ", ".join(sorted(missing))
        )

    if value["schema_version"] != SCHEMA_VERSION:
        raise PasswordRecoveryError(
            "unsupported password recovery schema"
        )

    recovery_id = str(value["recovery_id"])
    if (
        not recovery_id.startswith("pwd_")
        or len(recovery_id) != 36
    ):
        raise PasswordRecoveryError(
            "invalid password recovery ID"
        )

    token_hash = str(value["token_hash"])
    if (
        len(token_hash) != 64
        or any(
            character not in "0123456789abcdef"
            for character in token_hash
        )
    ):
        raise PasswordRecoveryError(
            "invalid password recovery token hash"
        )

    status = str(value["status"])
    if status not in VALID_STATUSES:
        raise PasswordRecoveryError(
            "invalid password recovery status"
        )

    created_at = _required_timestamp(
        value["created_at"],
        "created_at",
    )
    expires_at = _required_timestamp(
        value["expires_at"],
        "expires_at",
    )

    if expires_at <= created_at:
        raise PasswordRecoveryError(
            "password recovery expiration must follow creation"
        )

    normalized = dict(value)
    normalized["recovery_id"] = recovery_id
    normalized["token_hash"] = token_hash
    normalized["user_id"] = _required_identifier(
        value["user_id"],
        "user_id",
    )
    normalized["status"] = status
    normalized["completed_at"] = _optional_timestamp(
        value["completed_at"],
        "completed_at",
    )
    normalized["revoked_at"] = _optional_timestamp(
        value["revoked_at"],
        "revoked_at",
    )

    if status == "pending" and (
        normalized["completed_at"] is not None
        or normalized["revoked_at"] is not None
    ):
        raise PasswordRecoveryError(
            "pending password recovery cannot contain "
            "completion metadata"
        )

    if (
        status == "completed"
        and normalized["completed_at"] is None
    ):
        raise PasswordRecoveryError(
            "completed password recovery requires completed_at"
        )

    if (
        status in {"revoked", "expired"}
        and normalized["revoked_at"] is None
    ):
        raise PasswordRecoveryError(
            f"{status} password recovery requires revoked_at"
        )

    return normalized


def default_store() -> PasswordRecoveryStore:
    return PasswordRecoveryStore(
        default_identity_paths()
    )


def _expiration(
    record: Mapping[str, Any],
) -> datetime:
    return _required_timestamp(
        record["expires_at"],
        "expires_at",
    )


def _required_timestamp(
    value: object,
    field: str,
) -> datetime:
    parsed = (
        parse_timestamp(str(value))
        if value is not None
        else None
    )

    if parsed is None:
        raise PasswordRecoveryError(
            f"invalid {field}"
        )

    return parsed


def _optional_timestamp(
    value: object,
    field: str,
) -> str | None:
    if value is None:
        return None

    return format_timestamp(
        _required_timestamp(value, field)
    )


def _required_identifier(
    value: object,
    field: str,
) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise PasswordRecoveryError(
            f"{field} is required"
        )
    return normalized


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise PasswordRecoveryError(
            "password recovery clock must be timezone-aware"
        )
    return value


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)

    if not isinstance(value, dict):
        raise PasswordRecoveryError(
            f"invalid password recovery JSON: {path}"
        )

    return value
