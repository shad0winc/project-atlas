"""Atlas user identity and profile storage.

Atlas profiles extend, but do not replace, Jellyfin identities. Passwords and
other authentication secrets are intentionally outside this subsystem.

Profile schema version 2 introduces multiple roles and explicit permission
overrides. Version 1 profiles are migrated transparently when read.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


REGISTRY_SCHEMA_VERSION = 1
PROFILE_SCHEMA_VERSION = 2
LEGACY_PROFILE_SCHEMA_VERSION = 1

# Retained for callers that historically used SCHEMA_VERSION for the registry.
SCHEMA_VERSION = REGISTRY_SCHEMA_VERSION

LEGACY_ROLES = frozenset({"admin", "user"})

VALID_ROLES = frozenset(
    {
        "owner",
        "global_admin",
        "atlas_admin",
        "gameserver_admin",
        "monitoring_admin",
        "operator",
        "check_runner",
        "read_only",
        "member",
    }
)

ROLE_ALIASES = {
    "admin": "global_admin",
    "user": "member",
    "games_admin": "gameserver_admin",
    "readonly": "read_only",
}

VALID_STATUSES = frozenset({"active", "disabled"})

_USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_JELLYFIN_ID_PATTERN = re.compile(r"^[A-Fa-f0-9]{32}$")
_PERMISSION_COMPONENT_PATTERN = re.compile(r"^[a-z0-9_-]+$")


class UserProfileError(ValueError):
    """Raised when a user profile operation cannot be completed."""


@dataclass(frozen=True)
class UserProfileStore:
    """Durable Atlas user-profile store."""

    root: Path

    @property
    def registry_file(self) -> Path:
        return self.root / "users.json"

    @property
    def profiles_directory(self) -> Path:
        return self.root / "profiles"

    def initialize(self) -> None:
        self.root.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o2750,
        )
        self.profiles_directory.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o2750,
        )

        if not self.registry_file.exists():
            _atomic_write_json(
                self.registry_file,
                {
                    "schema_version": REGISTRY_SCHEMA_VERSION,
                    "users": {},
                },
            )

    def create_user(
        self,
        username: str,
        *,
        display_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        birthday: str | None = None,
        role: str | None = None,
        roles: Sequence[str] | None = None,
        permission_overrides: Mapping[str, Any] | None = None,
        status: str = "active",
        jellyfin_user_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a profile using the current schema.

        ``role`` remains available for legacy callers. New callers should pass
        ``roles``. The two arguments cannot be supplied together.
        """

        self.initialize()
        normalized_username = normalize_username(username)
        registry = self._load_registry()

        for entry in registry["users"].values():
            if entry["username"] == normalized_username:
                raise UserProfileError(
                    f"username already exists: {normalized_username}"
                )

        normalized_email = normalize_email(email)
        self._assert_unique_email(registry, normalized_email)

        normalized_roles = _roles_from_create_arguments(
            role=role,
            roles=roles,
        )

        user_id = f"usr_{uuid.uuid4().hex}"
        timestamp = _utc_now()

        profile = validate_profile(
            {
                "schema_version": PROFILE_SCHEMA_VERSION,
                "user_id": user_id,
                "username": normalized_username,
                "display_name": (
                    _clean_optional(display_name) or normalized_username
                ),
                "first_name": _clean_optional(first_name),
                "last_name": _clean_optional(last_name),
                "email": normalized_email,
                "birthday": normalize_birthday(birthday),
                "roles": list(normalized_roles),
                "permission_overrides": normalize_permission_overrides(
                    permission_overrides
                ),
                "status": normalize_status(status),
                "jellyfin_user_id": normalize_jellyfin_user_id(
                    jellyfin_user_id
                ),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )

        profile_file = self._profile_file(user_id)
        profile_file.parent.mkdir(
            parents=True,
            exist_ok=False,
            mode=0o2750,
        )

        try:
            _atomic_write_json(profile_file, profile)

            registry["users"][user_id] = {
                "username": profile["username"],
                "status": profile["status"],
                "profile": profile_file.relative_to(self.root).as_posix(),
            }

            _atomic_write_json(self.registry_file, registry)
        except Exception:
            try:
                profile_file.unlink(missing_ok=True)
                profile_file.parent.rmdir()
            except OSError:
                pass
            raise

        return profile

    def list_users(self) -> list[dict[str, Any]]:
        """Return all profiles ordered by username."""

        self.initialize()

        profiles = [
            self.get_user(user_id)
            for user_id in self._load_registry()["users"]
        ]

        return sorted(
            profiles,
            key=lambda profile: profile["username"],
        )

    def get_user(self, identifier: str) -> dict[str, Any]:
        """Read a profile and transparently persist schema migrations."""

        self.initialize()
        registry = self._load_registry()
        user_id = self._resolve_user_id(registry, identifier)

        profile_path = (
            self.root / registry["users"][user_id]["profile"]
        ).resolve()

        try:
            profile_path.relative_to(self.root.resolve())
        except ValueError as error:
            raise UserProfileError(
                f"profile path escapes user directory: {user_id}"
            ) from error

        raw_profile = _read_json(profile_path)
        profile = validate_profile(raw_profile)

        if raw_profile.get("schema_version") != PROFILE_SCHEMA_VERSION:
            _atomic_write_json(profile_path, profile)

        return profile

    def update_user(
        self,
        identifier: str,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Update a user profile using current-schema fields."""

        self.initialize()
        registry = self._load_registry()
        user_id = self._resolve_user_id(registry, identifier)
        current = self.get_user(user_id)

        supported = {
            "username",
            "display_name",
            "first_name",
            "last_name",
            "email",
            "birthday",
            "role",
            "roles",
            "permission_overrides",
            "granted_permissions",
            "denied_permissions",
            "status",
            "jellyfin_user_id",
        }

        unsupported = set(changes) - supported

        if unsupported:
            raise UserProfileError(
                "unsupported profile fields: "
                + ", ".join(sorted(unsupported))
            )

        if "role" in changes and "roles" in changes:
            raise UserProfileError(
                "role and roles cannot be updated together"
            )

        updated = dict(current)

        if "username" in changes:
            updated["username"] = normalize_username(
                str(changes["username"])
            )

            for other_id, entry in registry["users"].items():
                if (
                    other_id != user_id
                    and entry["username"] == updated["username"]
                ):
                    raise UserProfileError(
                        f"username already exists: {updated['username']}"
                    )

        for field in ("display_name", "first_name", "last_name"):
            if field in changes:
                updated[field] = _clean_optional(changes[field])

        if "display_name" in changes and not updated["display_name"]:
            updated["display_name"] = updated["username"]

        if "email" in changes:
            updated["email"] = normalize_email(changes["email"])
            self._assert_unique_email(
                registry,
                updated["email"],
                exclude_user_id=user_id,
            )

        if "birthday" in changes:
            updated["birthday"] = normalize_birthday(
                changes["birthday"]
            )

        requested_roles: tuple[str, ...] | None = None

        if "role" in changes:
            requested_roles = (
                normalize_profile_role(str(changes["role"])),
            )
        elif "roles" in changes:
            requested_roles = normalize_roles(changes["roles"])

        if requested_roles is not None:
            _protect_owner_role_change(
                current_roles=tuple(current["roles"]),
                requested_roles=requested_roles,
            )
            updated["roles"] = list(requested_roles)

        if "permission_overrides" in changes:
            updated["permission_overrides"] = (
                normalize_permission_overrides(
                    changes["permission_overrides"]
                )
            )

        if (
            "granted_permissions" in changes
            or "denied_permissions" in changes
        ):
            overrides = dict(updated["permission_overrides"])

            if "granted_permissions" in changes:
                overrides["allow"] = list(
                    normalize_permission_patterns(
                        changes["granted_permissions"]
                    )
                )

            if "denied_permissions" in changes:
                overrides["deny"] = list(
                    normalize_permission_patterns(
                        changes["denied_permissions"]
                    )
                )

            updated["permission_overrides"] = (
                normalize_permission_overrides(overrides)
            )

        if "status" in changes:
            requested_status = normalize_status(str(changes["status"]))

            if (
                "owner" in current["roles"]
                and requested_status != "active"
            ):
                raise UserProfileError(
                    "owner profiles cannot be disabled"
                )

            updated["status"] = requested_status

        if "jellyfin_user_id" in changes:
            updated["jellyfin_user_id"] = (
                normalize_jellyfin_user_id(
                    changes["jellyfin_user_id"]
                )
            )

        updated["updated_at"] = _utc_now()
        updated = validate_profile(updated)

        _atomic_write_json(self._profile_file(user_id), updated)

        registry["users"][user_id].update(
            username=updated["username"],
            status=updated["status"],
        )

        _atomic_write_json(self.registry_file, registry)
        return updated

    def delete_user(self, identifier: str) -> dict[str, Any]:
        """Delete a non-Owner profile and registry entry safely."""

        self.initialize()
        registry = self._load_registry()
        user_id = self._resolve_user_id(registry, identifier)
        profile = self.get_user(user_id)

        if "owner" in profile["roles"]:
            raise UserProfileError(
                "owner profiles cannot be deleted"
            )

        profile_directory = self._profile_file(user_id).parent
        staged_directory = (
            self.profiles_directory
            / f".{user_id}.deleting-{uuid.uuid4().hex}"
        )

        profile_directory.rename(staged_directory)

        updated_registry = dict(registry)
        updated_registry["users"] = dict(registry["users"])
        del updated_registry["users"][user_id]

        try:
            _atomic_write_json(
                self.registry_file,
                updated_registry,
            )
        except Exception:
            staged_directory.rename(profile_directory)
            raise

        shutil.rmtree(staged_directory)
        return profile

    def verify(self, identifier: str | None = None) -> list[str]:
        """Return storage consistency errors."""

        self.initialize()
        registry = self._load_registry()
        errors: list[str] = []

        identifiers = (
            [identifier]
            if identifier
            else list(registry["users"])
        )

        seen_usernames: set[str] = set()
        seen_emails: set[str] = set()

        for item in identifiers:
            try:
                user_id = self._resolve_user_id(
                    registry,
                    str(item),
                )
                profile = self.get_user(user_id)
                entry = registry["users"][user_id]

                if entry["username"] != profile["username"]:
                    errors.append(
                        f"{user_id}: registry username does not match profile"
                    )

                if entry["status"] != profile["status"]:
                    errors.append(
                        f"{user_id}: registry status does not match profile"
                    )

                if profile["username"] in seen_usernames:
                    errors.append(
                        f"{user_id}: duplicate username "
                        f"{profile['username']}"
                    )

                seen_usernames.add(profile["username"])

                if profile["email"]:
                    if profile["email"] in seen_emails:
                        errors.append(
                            f"{user_id}: duplicate email "
                            f"{profile['email']}"
                        )

                    seen_emails.add(profile["email"])
            except (
                OSError,
                json.JSONDecodeError,
                UserProfileError,
            ) as error:
                errors.append(f"{item}: {error}")

        return errors

    def _profile_file(self, user_id: str) -> Path:
        return (
            self.profiles_directory
            / user_id
            / "profile.json"
        )

    def _load_registry(self) -> dict[str, Any]:
        registry = _read_json(self.registry_file)

        if (
            not isinstance(registry, dict)
            or registry.get("schema_version")
            != REGISTRY_SCHEMA_VERSION
        ):
            raise UserProfileError(
                "unsupported user registry schema"
            )

        users = registry.get("users")

        if not isinstance(users, dict):
            raise UserProfileError(
                "user registry users must be an object"
            )

        for user_id, entry in users.items():
            if not isinstance(entry, dict):
                raise UserProfileError(
                    f"invalid registry entry: {user_id}"
                )

            if not isinstance(entry.get("username"), str):
                raise UserProfileError(
                    f"invalid registry username: {user_id}"
                )

            if entry.get("status") not in VALID_STATUSES:
                raise UserProfileError(
                    f"invalid registry status: {user_id}"
                )

            if not isinstance(entry.get("profile"), str):
                raise UserProfileError(
                    f"invalid registry profile path: {user_id}"
                )

        return registry

    @staticmethod
    def _resolve_user_id(
        registry: Mapping[str, Any],
        identifier: str,
    ) -> str:
        normalized = identifier.strip().lower()

        if identifier in registry["users"]:
            return identifier

        matches = [
            user_id
            for user_id, entry in registry["users"].items()
            if entry["username"] == normalized
        ]

        if len(matches) == 1:
            return matches[0]

        raise UserProfileError(
            f"user not found: {identifier}"
        )

    def _assert_unique_email(
        self,
        registry: Mapping[str, Any],
        email: str | None,
        *,
        exclude_user_id: str | None = None,
    ) -> None:
        if not email:
            return

        for user_id in registry["users"]:
            if user_id == exclude_user_id:
                continue

            if self.get_user(user_id).get("email") == email:
                raise UserProfileError(
                    f"email already exists: {email}"
                )


def normalize_username(value: str) -> str:
    """Normalize and validate an Atlas username."""

    username = value.strip().lower()

    if not _USERNAME_PATTERN.fullmatch(username):
        raise UserProfileError(
            "username must be 3-32 characters using lowercase letters, "
            "numbers, '.', '_' or '-'"
        )

    return username


def normalize_email(value: object) -> str | None:
    """Normalize an optional email address."""

    email = _clean_optional(value)

    if email is None:
        return None

    email = email.lower()

    if (
        len(email) > 254
        or not _EMAIL_PATTERN.fullmatch(email)
    ):
        raise UserProfileError("invalid email address")

    return email


def normalize_birthday(value: object) -> str | None:
    """Normalize an optional ISO birthday."""

    birthday = _clean_optional(value)

    if birthday is None:
        return None

    try:
        parsed = date.fromisoformat(birthday)
    except ValueError as error:
        raise UserProfileError(
            "birthday must use YYYY-MM-DD"
        ) from error

    if parsed > date.today():
        raise UserProfileError(
            "birthday cannot be in the future"
        )

    return parsed.isoformat()


def normalize_role(value: str) -> str:
    """Validate one legacy invitation or provisioning role.

    Invitations continue using ``admin`` and ``user`` until their own schema
    migration. This preserves compatibility with external provisioners.
    """

    role = value.strip().lower()

    if role not in LEGACY_ROLES:
        raise UserProfileError(
            "role must be one of: "
            + ", ".join(sorted(LEGACY_ROLES))
        )

    return role


def normalize_profile_role(value: str) -> str:
    """Normalize one current Atlas profile role."""

    role = value.strip().lower()

    if not role:
        raise UserProfileError(
            "profile role cannot be empty"
        )

    role = ROLE_ALIASES.get(role, role)

    if role not in VALID_ROLES:
        raise UserProfileError(
            "profile role must be one of: "
            + ", ".join(sorted(VALID_ROLES))
        )

    return role


def normalize_roles(value: object) -> tuple[str, ...]:
    """Normalize, validate, and deduplicate profile roles."""

    if isinstance(value, str):
        raw_roles: Iterable[object] = (
            item
            for item in value.split(",")
        )
    elif isinstance(value, Sequence):
        raw_roles = value
    else:
        raise UserProfileError(
            "roles must be a list of role names"
        )

    normalized: list[str] = []
    seen: set[str] = set()

    for raw_role in raw_roles:
        role = normalize_profile_role(str(raw_role))

        if role not in seen:
            normalized.append(role)
            seen.add(role)

    if not normalized:
        raise UserProfileError(
            "at least one profile role is required"
        )

    return tuple(normalized)


def normalize_permission_pattern(value: object) -> str:
    """Normalize one permission pattern."""

    pattern = str(value).strip().lower()

    if not pattern:
        raise UserProfileError(
            "permission pattern cannot be empty"
        )

    if pattern == "*":
        return pattern

    components = pattern.split(".")

    if len(components) < 2:
        raise UserProfileError(
            "permission patterns require a namespace and action"
        )

    if components.count("*") > 1:
        raise UserProfileError(
            "permission patterns may contain at most one wildcard"
        )

    for component in components:
        if component == "*":
            continue

        if not _PERMISSION_COMPONENT_PATTERN.fullmatch(
            component
        ):
            raise UserProfileError(
                "permission components may contain only lowercase "
                "letters, numbers, underscores, and hyphens"
            )

    return pattern


def normalize_permission_patterns(
    value: object,
) -> tuple[str, ...]:
    """Normalize and deduplicate a permission-pattern collection."""

    if value is None:
        return ()

    if isinstance(value, str):
        raw_patterns: Iterable[object] = (
            item
            for item in value.split(",")
        )
    elif isinstance(value, Sequence):
        raw_patterns = value
    else:
        raise UserProfileError(
            "permission patterns must be a list"
        )

    normalized: list[str] = []
    seen: set[str] = set()

    for raw_pattern in raw_patterns:
        pattern = normalize_permission_pattern(raw_pattern)

        if pattern not in seen:
            normalized.append(pattern)
            seen.add(pattern)

    return tuple(normalized)


def normalize_permission_overrides(
    value: object,
) -> dict[str, list[str]]:
    """Normalize profile permission allow and deny overrides."""

    if value is None:
        return {
            "allow": [],
            "deny": [],
        }

    if not isinstance(value, Mapping):
        raise UserProfileError(
            "permission_overrides must be an object"
        )

    unsupported = set(value) - {"allow", "deny"}

    if unsupported:
        raise UserProfileError(
            "unsupported permission override fields: "
            + ", ".join(sorted(str(item) for item in unsupported))
        )

    allow = normalize_permission_patterns(
        value.get("allow", ())
    )
    deny = normalize_permission_patterns(
        value.get("deny", ())
    )

    return {
        "allow": list(allow),
        "deny": list(deny),
    }


def normalize_status(value: str) -> str:
    """Normalize profile status."""

    status = value.strip().lower()

    if status not in VALID_STATUSES:
        raise UserProfileError(
            "status must be one of: "
            + ", ".join(sorted(VALID_STATUSES))
        )

    return status


def normalize_jellyfin_user_id(
    value: object,
) -> str | None:
    """Normalize an optional Jellyfin user ID."""

    jellyfin_id = _clean_optional(value)

    if jellyfin_id is None:
        return None

    if not _JELLYFIN_ID_PATTERN.fullmatch(jellyfin_id):
        raise UserProfileError(
            "Jellyfin user ID must be a "
            "32-character hexadecimal value"
        )

    return jellyfin_id.lower()


def validate_profile(
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and normalize a current or legacy profile."""

    schema_version = profile.get("schema_version")

    if schema_version == LEGACY_PROFILE_SCHEMA_VERSION:
        return _migrate_legacy_profile(profile)

    if schema_version != PROFILE_SCHEMA_VERSION:
        raise UserProfileError(
            "unsupported user profile schema"
        )

    required = {
        "schema_version",
        "user_id",
        "username",
        "display_name",
        "first_name",
        "last_name",
        "email",
        "birthday",
        "roles",
        "permission_overrides",
        "status",
        "jellyfin_user_id",
        "created_at",
        "updated_at",
    }

    missing = required - set(profile)

    if missing:
        raise UserProfileError(
            "profile is missing fields: "
            + ", ".join(sorted(missing))
        )

    normalized = dict(profile)
    normalized["schema_version"] = PROFILE_SCHEMA_VERSION

    _validate_profile_identity(normalized)

    normalized["username"] = normalize_username(
        str(profile["username"])
    )
    normalized["display_name"] = (
        _clean_optional(profile["display_name"])
        or normalized["username"]
    )
    normalized["first_name"] = _clean_optional(
        profile["first_name"]
    )
    normalized["last_name"] = _clean_optional(
        profile["last_name"]
    )
    normalized["email"] = normalize_email(
        profile["email"]
    )
    normalized["birthday"] = normalize_birthday(
        profile["birthday"]
    )
    normalized["roles"] = list(
        normalize_roles(profile["roles"])
    )
    normalized["permission_overrides"] = (
        normalize_permission_overrides(
            profile["permission_overrides"]
        )
    )
    normalized["status"] = normalize_status(
        str(profile["status"])
    )
    normalized["jellyfin_user_id"] = (
        normalize_jellyfin_user_id(
            profile["jellyfin_user_id"]
        )
    )

    _validate_profile_timestamps(normalized)
    return normalized


def default_store() -> UserProfileStore:
    """Return the default Atlas user-profile store."""

    root = Path(
        os.getenv(
            "ATLAS_USERS_DIR",
            "/mnt/storage/configs/atlas/users",
        )
    ).expanduser()

    return UserProfileStore(root.resolve())


def _roles_from_create_arguments(
    *,
    role: str | None,
    roles: Sequence[str] | None,
) -> tuple[str, ...]:
    if role is not None and roles is not None:
        raise UserProfileError(
            "role and roles cannot be provided together"
        )

    if roles is not None:
        return normalize_roles(roles)

    if role is not None:
        return (
            normalize_profile_role(role),
        )

    return ("member",)


def _protect_owner_role_change(
    *,
    current_roles: tuple[str, ...],
    requested_roles: tuple[str, ...],
) -> None:
    if (
        "owner" in current_roles
        and "owner" not in requested_roles
    ):
        raise UserProfileError(
            "the owner role cannot be removed"
        )


def _migrate_legacy_profile(
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "schema_version",
        "user_id",
        "username",
        "display_name",
        "first_name",
        "last_name",
        "email",
        "birthday",
        "role",
        "status",
        "jellyfin_user_id",
        "created_at",
        "updated_at",
    }

    missing = required - set(profile)

    if missing:
        raise UserProfileError(
            "profile is missing fields: "
            + ", ".join(sorted(missing))
        )

    migrated = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "user_id": profile["user_id"],
        "username": profile["username"],
        "display_name": profile["display_name"],
        "first_name": profile["first_name"],
        "last_name": profile["last_name"],
        "email": profile["email"],
        "birthday": profile["birthday"],
        "roles": [
            normalize_profile_role(
                normalize_role(str(profile["role"]))
            )
        ],
        "permission_overrides": {
            "allow": [],
            "deny": [],
        },
        "status": profile["status"],
        "jellyfin_user_id": profile["jellyfin_user_id"],
        "created_at": profile["created_at"],
        "updated_at": profile["updated_at"],
    }

    return validate_profile(migrated)


def _validate_profile_identity(
    profile: Mapping[str, Any],
) -> None:
    user_id = profile.get("user_id")

    if (
        not isinstance(user_id, str)
        or not user_id.startswith("usr_")
    ):
        raise UserProfileError("invalid user ID")


def _validate_profile_timestamps(
    profile: Mapping[str, Any],
) -> None:
    for field in ("created_at", "updated_at"):
        try:
            datetime.fromisoformat(
                str(profile[field]).replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError as error:
            raise UserProfileError(
                f"invalid {field}"
            ) from error


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()
    return cleaned or None


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )
    except FileNotFoundError as error:
        raise UserProfileError(
            f"missing user data file: {path}"
        ) from error
    except json.JSONDecodeError as error:
        raise UserProfileError(
            f"invalid JSON file: {path}"
        ) from error

    if not isinstance(data, dict):
        raise UserProfileError(
            f"JSON root must be an object: {path}"
        )

    return data


def _atomic_write_json(
    path: Path,
    value: Mapping[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o2750,
    )

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(
            descriptor,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                value,
                handle,
                indent=2,
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.chmod(temporary_path, 0o640)

        os.replace(
            temporary_path,
            path,
        )
    finally:
        temporary_path.unlink(missing_ok=True)
