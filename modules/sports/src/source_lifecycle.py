"""Authoritative metadata contract for Atlas Sports delivery sources.

This registry contains lifecycle and routing metadata only. Provider URLs,
usernames, passwords, access tokens, API keys, stream URLs, and other source
credentials must never be persisted here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Iterable
from urllib.parse import urlsplit


SCHEMA_VERSION = 1
MAX_CANDIDATES = 4
PRIMARY_RENEWAL_NOTICE_DAYS = 14
DEFAULT_RENEWAL_NOTICE_DAYS = (30, 14, 7, 3, 1)

_ALLOWED_SOURCE_FIELDS = frozenset(
    {
        "source_id",
        "display_name",
        "kind",
        "trust_class",
        "enabled",
        "priority",
        "max_connections",
        "backend_reference",
        "purchased_at",
        "expires_at",
        "renewal_url",
        "renewal_notice_days",
    }
)


class SourceLifecycleError(ValueError):
    """Raised when source lifecycle state violates the v1 contract."""


class SourceKind(StrEnum):
    LICENSED_SUBSCRIPTION = "licensed_subscription"
    OFFICIAL_FREE = "official_free"
    USER_OWNED_OTA = "user_owned_ota"
    COMMUNITY_PUBLIC = "community_public"


class TrustClass(StrEnum):
    LICENSED = "licensed"
    OFFICIAL = "official"
    USER_OWNED = "user_owned"
    COMMUNITY_PUBLIC = "community_public"


_KIND_TRUST = {
    SourceKind.LICENSED_SUBSCRIPTION: TrustClass.LICENSED,
    SourceKind.OFFICIAL_FREE: TrustClass.OFFICIAL,
    SourceKind.USER_OWNED_OTA: TrustClass.USER_OWNED,
    SourceKind.COMMUNITY_PUBLIC: TrustClass.COMMUNITY_PUBLIC,
}

_KIND_ORDER = {
    SourceKind.LICENSED_SUBSCRIPTION: 0,
    SourceKind.OFFICIAL_FREE: 1,
    SourceKind.USER_OWNED_OTA: 2,
    SourceKind.COMMUNITY_PUBLIC: 3,
}


def default_source_lifecycle_path() -> Path:
    return Path(
        os.environ.get(
            "SPORTS_SOURCE_LIFECYCLE_FILE",
            "/mnt/storage/configs/sportyfin/state/source-lifecycle.json",
        )
    )


def _required_text(value: object, field: str, *, max_length: int = 128) -> str:
    text = str(value or "").strip()
    if not text:
        raise SourceLifecycleError(f"{field} is required")
    if len(text) > max_length:
        raise SourceLifecycleError(
            f"{field} must be at most {max_length} characters"
        )
    return text


def _optional_text(
    value: object,
    field: str,
    *,
    max_length: int = 256,
) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_length:
        raise SourceLifecycleError(
            f"{field} must be at most {max_length} characters"
        )
    return text


def _parse_iso8601(value: object, field: str) -> str | None:
    text = _optional_text(value, field, max_length=64)
    if text is None:
        return None

    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise SourceLifecycleError(
            f"{field} must be an ISO-8601 timestamp"
        ) from exc

    if parsed.tzinfo is None:
        raise SourceLifecycleError(
            f"{field} must include a timezone"
        )

    return parsed.astimezone(timezone.utc).isoformat().replace(
        "+00:00",
        "Z",
    )


def _renewal_url(value: object) -> str | None:
    text = _optional_text(value, "renewal_url", max_length=2048)
    if text is None:
        return None

    parsed = urlsplit(text)

    if parsed.scheme not in {"http", "https"}:
        raise SourceLifecycleError(
            "renewal_url must use http or https"
        )

    if not parsed.hostname:
        raise SourceLifecycleError(
            "renewal_url must include a hostname"
        )

    if parsed.username is not None or parsed.password is not None:
        raise SourceLifecycleError(
            "renewal_url must not contain embedded credentials"
        )

    return text


def _positive_int(
    value: object,
    field: str,
    *,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool):
        raise SourceLifecycleError(f"{field} must be an integer")

    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise SourceLifecycleError(
            f"{field} must be an integer"
        ) from exc

    if parsed < minimum or parsed > maximum:
        raise SourceLifecycleError(
            f"{field} must be between {minimum} and {maximum}"
        )

    return parsed


def _notice_days(value: object) -> tuple[int, ...]:
    if value is None:
        return DEFAULT_RENEWAL_NOTICE_DAYS

    if not isinstance(value, (list, tuple)):
        raise SourceLifecycleError(
            "renewal_notice_days must be a list"
        )

    days = tuple(
        sorted(
            {
                _positive_int(
                    item,
                    "renewal_notice_days",
                    minimum=1,
                    maximum=365,
                )
                for item in value
            },
            reverse=True,
        )
    )

    if PRIMARY_RENEWAL_NOTICE_DAYS not in days:
        raise SourceLifecycleError(
            "renewal_notice_days must include the primary "
            "14-day warning"
        )

    return days


@dataclass(frozen=True, slots=True)
class SportsSource:
    source_id: str
    display_name: str
    kind: SourceKind
    trust_class: TrustClass
    enabled: bool
    priority: int
    max_connections: int
    backend_reference: str | None = None
    purchased_at: str | None = None
    expires_at: str | None = None
    renewal_url: str | None = None
    renewal_notice_days: tuple[int, ...] = DEFAULT_RENEWAL_NOTICE_DAYS

    @classmethod
    def from_mapping(cls, raw: dict[str, Any]) -> "SportsSource":
        if not isinstance(raw, dict):
            raise SourceLifecycleError(
                "source must be an object"
            )

        unexpected = sorted(
            set(raw) - _ALLOWED_SOURCE_FIELDS
        )

        if unexpected:
            raise SourceLifecycleError(
                "unsupported source fields: "
                + ", ".join(unexpected)
            )

        source_id = _required_text(
            raw.get("source_id"),
            "source_id",
            max_length=64,
        )
        display_name = _required_text(
            raw.get("display_name"),
            "display_name",
            max_length=128,
        )

        try:
            kind = SourceKind(
                _required_text(
                    raw.get("kind"),
                    "kind",
                    max_length=64,
                )
            )
        except ValueError as exc:
            raise SourceLifecycleError(
                "unsupported source kind"
            ) from exc

        expected_trust = _KIND_TRUST[kind]

        raw_trust = raw.get("trust_class")
        if raw_trust is None:
            trust = expected_trust
        else:
            try:
                trust = TrustClass(str(raw_trust).strip())
            except ValueError as exc:
                raise SourceLifecycleError(
                    "unsupported trust_class"
                ) from exc

            if trust is not expected_trust:
                raise SourceLifecycleError(
                    "trust_class does not match source kind"
                )

        enabled = raw.get("enabled", True)
        if not isinstance(enabled, bool):
            raise SourceLifecycleError(
                "enabled must be boolean"
            )

        priority = _positive_int(
            raw.get("priority", 100),
            "priority",
            minimum=0,
            maximum=10000,
        )

        max_connections = _positive_int(
            raw.get("max_connections", 1),
            "max_connections",
            minimum=1,
            maximum=1000,
        )

        purchased_at = _parse_iso8601(
            raw.get("purchased_at"),
            "purchased_at",
        )
        expires_at = _parse_iso8601(
            raw.get("expires_at"),
            "expires_at",
        )

        if kind is not SourceKind.LICENSED_SUBSCRIPTION:
            if purchased_at is not None or expires_at is not None:
                raise SourceLifecycleError(
                    "purchase/expiration metadata is only valid "
                    "for licensed subscriptions"
                )

        return cls(
            source_id=source_id,
            display_name=display_name,
            kind=kind,
            trust_class=trust,
            enabled=enabled,
            priority=priority,
            max_connections=max_connections,
            backend_reference=_optional_text(
                raw.get("backend_reference"),
                "backend_reference",
                max_length=128,
            ),
            purchased_at=purchased_at,
            expires_at=expires_at,
            renewal_url=_renewal_url(
                raw.get("renewal_url")
            ),
            renewal_notice_days=_notice_days(
                raw.get("renewal_notice_days")
            ),
        )

    def to_mapping(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "display_name": self.display_name,
            "kind": self.kind.value,
            "trust_class": self.trust_class.value,
            "enabled": self.enabled,
            "priority": self.priority,
            "max_connections": self.max_connections,
            "backend_reference": self.backend_reference,
            "purchased_at": self.purchased_at,
            "expires_at": self.expires_at,
            "renewal_url": self.renewal_url,
            "renewal_notice_days": list(
                self.renewal_notice_days
            ),
        }


@dataclass(frozen=True, slots=True)
class SourceCandidate:
    source_id: str
    slot: int
    priority: int
    kind: SourceKind

    def to_mapping(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "slot": self.slot,
            "priority": self.priority,
            "kind": self.kind.value,
        }


def rank_source_candidates(
    sources: Iterable[SportsSource],
) -> tuple[SourceCandidate, ...]:
    enabled = [
        source
        for source in sources
        if source.enabled
    ]

    enabled.sort(
        key=lambda source: (
            _KIND_ORDER[source.kind],
            source.priority,
            source.source_id,
        )
    )

    selected = enabled[:MAX_CANDIDATES]

    return tuple(
        SourceCandidate(
            source_id=source.source_id,
            slot=index,
            priority=source.priority,
            kind=source.kind,
        )
        for index, source in enumerate(
            selected,
            start=1,
        )
    )


class SourceLifecycleStore:
    """Atomic JSON store for non-secret Sports source metadata."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_source_lifecycle_path()

    def _validate_existing_path(self) -> None:
        if self.path.is_symlink():
            raise SourceLifecycleError(
                "source lifecycle state must not "
                "be a symbolic link"
            )

        if (
            self.path.exists()
            and not self.path.is_file()
        ):
            raise SourceLifecycleError(
                "source lifecycle state must be "
                "a regular file"
            )

    def ensure(self) -> tuple[SportsSource, ...]:
        self._validate_existing_path()

        if self.path.exists():
            return self.load()

        self.write(())
        return ()

    def load(self) -> tuple[SportsSource, ...]:
        self._validate_existing_path()

        if not self.path.exists():
            return ()

        try:
            raw = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            raise SourceLifecycleError(
                "source lifecycle state is unreadable"
            ) from exc

        if not isinstance(raw, dict):
            raise SourceLifecycleError(
                "source lifecycle root must be an object"
            )

        if raw.get("version") != SCHEMA_VERSION:
            raise SourceLifecycleError(
                "unsupported source lifecycle version"
            )

        values = raw.get("sources")

        if not isinstance(values, list):
            raise SourceLifecycleError(
                "sources must be a list"
            )

        sources = tuple(
            SportsSource.from_mapping(value)
            for value in values
        )

        ids = [source.source_id for source in sources]
        if len(ids) != len(set(ids)):
            raise SourceLifecycleError(
                "source_id values must be unique"
            )

        return sources

    def write(
        self,
        sources: Iterable[SportsSource],
    ) -> None:
        self._validate_existing_path()

        values = tuple(sources)

        ids = [source.source_id for source in values]
        if len(ids) != len(set(ids)):
            raise SourceLifecycleError(
                "source_id values must be unique"
            )

        payload = {
            "version": SCHEMA_VERSION,
            "sources": [
                source.to_mapping()
                for source in sorted(
                    values,
                    key=lambda source: source.source_id,
                )
            ],
        }

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
            mode=0o750,
        )

        rendered = (
            json.dumps(
                payload,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )

        fd, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            dir=str(self.path.parent),
            text=True,
        )

        temporary = Path(temporary_name)

        try:
            os.fchmod(fd, 0o600)

            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as handle:
                handle.write(rendered)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(
                temporary,
                self.path,
            )
            os.chmod(
                self.path,
                0o600,
            )

            directory_fd = os.open(
                self.path.parent,
                os.O_RDONLY,
            )
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        finally:
            temporary.unlink(
                missing_ok=True
            )
