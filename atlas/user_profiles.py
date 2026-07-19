"""Atlas user identity and profile storage.

Atlas profiles extend, but do not replace, Jellyfin identities. Passwords and
other authentication secrets are intentionally outside this subsystem.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = 1
VALID_ROLES = frozenset({"admin", "user"})
VALID_STATUSES = frozenset({"active", "disabled"})
_USERNAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_JELLYFIN_ID_PATTERN = re.compile(r"^[A-Fa-f0-9]{32}$")


class UserProfileError(ValueError):
    """Raised when a user profile operation cannot be completed."""


@dataclass(frozen=True)
class UserProfileStore:
    root: Path

    @property
    def registry_file(self) -> Path:
        return self.root / "users.json"

    @property
    def profiles_directory(self) -> Path:
        return self.root / "profiles"

    def initialize(self) -> None:
        self.profiles_directory.mkdir(parents=True, exist_ok=True)
        if not self.registry_file.exists():
            _atomic_write_json(
                self.registry_file,
                {"schema_version": SCHEMA_VERSION, "users": {}},
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
        role: str = "user",
        status: str = "active",
        jellyfin_user_id: str | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        normalized_username = normalize_username(username)
        registry = self._load_registry()

        for entry in registry["users"].values():
            if entry["username"] == normalized_username:
                raise UserProfileError(f"username already exists: {normalized_username}")

        normalized_email = normalize_email(email)
        self._assert_unique_email(registry, normalized_email)

        user_id = f"usr_{uuid.uuid4().hex}"
        timestamp = _utc_now()
        profile = validate_profile(
            {
                "schema_version": SCHEMA_VERSION,
                "user_id": user_id,
                "username": normalized_username,
                "display_name": _clean_optional(display_name) or normalized_username,
                "first_name": _clean_optional(first_name),
                "last_name": _clean_optional(last_name),
                "email": normalized_email,
                "birthday": normalize_birthday(birthday),
                "role": normalize_role(role),
                "status": normalize_status(status),
                "jellyfin_user_id": normalize_jellyfin_user_id(jellyfin_user_id),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )

        profile_file = self._profile_file(user_id)
        profile_file.parent.mkdir(parents=True, exist_ok=False)
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
        self.initialize()
        profiles = [self.get_user(user_id) for user_id in self._load_registry()["users"]]
        return sorted(profiles, key=lambda profile: profile["username"])

    def get_user(self, identifier: str) -> dict[str, Any]:
        self.initialize()
        registry = self._load_registry()
        user_id = self._resolve_user_id(registry, identifier)
        profile_path = (self.root / registry["users"][user_id]["profile"]).resolve()
        try:
            profile_path.relative_to(self.root.resolve())
        except ValueError as exc:
            raise UserProfileError(f"profile path escapes user directory: {user_id}") from exc
        return validate_profile(_read_json(profile_path))

    def update_user(self, identifier: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        self.initialize()
        registry = self._load_registry()
        user_id = self._resolve_user_id(registry, identifier)
        current = self.get_user(user_id)

        unsupported = set(changes) - {
            "username", "display_name", "first_name", "last_name", "email",
            "birthday", "role", "status", "jellyfin_user_id",
        }
        if unsupported:
            raise UserProfileError(
                "unsupported profile fields: " + ", ".join(sorted(unsupported))
            )

        updated = dict(current)
        if "username" in changes:
            updated["username"] = normalize_username(str(changes["username"]))
            for other_id, entry in registry["users"].items():
                if other_id != user_id and entry["username"] == updated["username"]:
                    raise UserProfileError(f"username already exists: {updated['username']}")
        for field in ("display_name", "first_name", "last_name"):
            if field in changes:
                updated[field] = _clean_optional(changes[field])
        if "display_name" in changes and not updated["display_name"]:
            updated["display_name"] = updated["username"]
        if "email" in changes:
            updated["email"] = normalize_email(changes["email"])
            self._assert_unique_email(registry, updated["email"], exclude_user_id=user_id)
        if "birthday" in changes:
            updated["birthday"] = normalize_birthday(changes["birthday"])
        if "role" in changes:
            updated["role"] = normalize_role(str(changes["role"]))
        if "status" in changes:
            updated["status"] = normalize_status(str(changes["status"]))
        if "jellyfin_user_id" in changes:
            updated["jellyfin_user_id"] = normalize_jellyfin_user_id(
                changes["jellyfin_user_id"]
            )

        updated["updated_at"] = _utc_now()
        updated = validate_profile(updated)
        _atomic_write_json(self._profile_file(user_id), updated)
        registry["users"][user_id].update(
            username=updated["username"], status=updated["status"]
        )
        _atomic_write_json(self.registry_file, registry)
        return updated

    def verify(self, identifier: str | None = None) -> list[str]:
        self.initialize()
        registry = self._load_registry()
        errors: list[str] = []
        identifiers = [identifier] if identifier else list(registry["users"])
        seen_usernames: set[str] = set()
        seen_emails: set[str] = set()

        for item in identifiers:
            try:
                user_id = self._resolve_user_id(registry, str(item))
                profile = self.get_user(user_id)
                entry = registry["users"][user_id]
                if entry["username"] != profile["username"]:
                    errors.append(f"{user_id}: registry username does not match profile")
                if entry["status"] != profile["status"]:
                    errors.append(f"{user_id}: registry status does not match profile")
                if profile["username"] in seen_usernames:
                    errors.append(f"{user_id}: duplicate username {profile['username']}")
                seen_usernames.add(profile["username"])
                if profile["email"]:
                    if profile["email"] in seen_emails:
                        errors.append(f"{user_id}: duplicate email {profile['email']}")
                    seen_emails.add(profile["email"])
            except (OSError, json.JSONDecodeError, UserProfileError) as exc:
                errors.append(f"{item}: {exc}")
        return errors

    def _profile_file(self, user_id: str) -> Path:
        return self.profiles_directory / user_id / "profile.json"

    def _load_registry(self) -> dict[str, Any]:
        registry = _read_json(self.registry_file)
        if not isinstance(registry, dict) or registry.get("schema_version") != SCHEMA_VERSION:
            raise UserProfileError("unsupported user registry schema")
        users = registry.get("users")
        if not isinstance(users, dict):
            raise UserProfileError("user registry users must be an object")
        for user_id, entry in users.items():
            if not isinstance(entry, dict):
                raise UserProfileError(f"invalid registry entry: {user_id}")
            if not isinstance(entry.get("username"), str):
                raise UserProfileError(f"invalid registry username: {user_id}")
            if entry.get("status") not in VALID_STATUSES:
                raise UserProfileError(f"invalid registry status: {user_id}")
            if not isinstance(entry.get("profile"), str):
                raise UserProfileError(f"invalid registry profile path: {user_id}")
        return registry

    @staticmethod
    def _resolve_user_id(registry: Mapping[str, Any], identifier: str) -> str:
        normalized = identifier.strip().lower()
        if identifier in registry["users"]:
            return identifier
        matches = [
            user_id for user_id, entry in registry["users"].items()
            if entry["username"] == normalized
        ]
        if len(matches) == 1:
            return matches[0]
        raise UserProfileError(f"user not found: {identifier}")

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
                raise UserProfileError(f"email already exists: {email}")


def normalize_username(value: str) -> str:
    username = value.strip().lower()
    if not _USERNAME_PATTERN.fullmatch(username):
        raise UserProfileError(
            "username must be 3-32 characters using lowercase letters, numbers, '.', '_' or '-'"
        )
    return username


def normalize_email(value: object) -> str | None:
    email = _clean_optional(value)
    if email is None:
        return None
    email = email.lower()
    if len(email) > 254 or not _EMAIL_PATTERN.fullmatch(email):
        raise UserProfileError("invalid email address")
    return email


def normalize_birthday(value: object) -> str | None:
    birthday = _clean_optional(value)
    if birthday is None:
        return None
    try:
        parsed = date.fromisoformat(birthday)
    except ValueError as exc:
        raise UserProfileError("birthday must use YYYY-MM-DD") from exc
    if parsed > date.today():
        raise UserProfileError("birthday cannot be in the future")
    return parsed.isoformat()


def normalize_role(value: str) -> str:
    role = value.strip().lower()
    if role not in VALID_ROLES:
        raise UserProfileError("role must be one of: " + ", ".join(sorted(VALID_ROLES)))
    return role


def normalize_status(value: str) -> str:
    status = value.strip().lower()
    if status not in VALID_STATUSES:
        raise UserProfileError(
            "status must be one of: " + ", ".join(sorted(VALID_STATUSES))
        )
    return status


def normalize_jellyfin_user_id(value: object) -> str | None:
    jellyfin_id = _clean_optional(value)
    if jellyfin_id is None:
        return None
    if not _JELLYFIN_ID_PATTERN.fullmatch(jellyfin_id):
        raise UserProfileError("Jellyfin user ID must be a 32-character hexadecimal value")
    return jellyfin_id.lower()


def validate_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version", "user_id", "username", "display_name", "first_name",
        "last_name", "email", "birthday", "role", "status",
        "jellyfin_user_id", "created_at", "updated_at",
    }
    missing = required - set(profile)
    if missing:
        raise UserProfileError("profile is missing fields: " + ", ".join(sorted(missing)))
    if profile["schema_version"] != SCHEMA_VERSION:
        raise UserProfileError("unsupported user profile schema")
    if not isinstance(profile["user_id"], str) or not profile["user_id"].startswith("usr_"):
        raise UserProfileError("invalid user ID")

    normalized = dict(profile)
    normalized["username"] = normalize_username(str(profile["username"]))
    normalized["display_name"] = _clean_optional(profile["display_name"]) or normalized["username"]
    normalized["first_name"] = _clean_optional(profile["first_name"])
    normalized["last_name"] = _clean_optional(profile["last_name"])
    normalized["email"] = normalize_email(profile["email"])
    normalized["birthday"] = normalize_birthday(profile["birthday"])
    normalized["role"] = normalize_role(str(profile["role"]))
    normalized["status"] = normalize_status(str(profile["status"]))
    normalized["jellyfin_user_id"] = normalize_jellyfin_user_id(profile["jellyfin_user_id"])
    for field in ("created_at", "updated_at"):
        try:
            datetime.fromisoformat(str(profile[field]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise UserProfileError(f"invalid {field}") from exc
    return normalized


def default_store() -> UserProfileStore:
    root = Path(
        os.getenv("ATLAS_USERS_DIR", "/mnt/storage/configs/atlas/users")
    ).expanduser()
    return UserProfileStore(root.resolve())


def _clean_optional(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise UserProfileError(f"missing user data file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise UserProfileError(f"invalid JSON file: {path}") from exc
    if not isinstance(data, dict):
        raise UserProfileError(f"JSON root must be an object: {path}")
    return data


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
