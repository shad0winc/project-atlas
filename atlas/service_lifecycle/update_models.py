"""Normalized update-discovery contracts for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any

from .models import ServiceLifecycleError


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)
_DIGEST_PATTERN = re.compile(r"^[a-z0-9][a-z0-9+._-]*:[a-f0-9]{32,}$")


class UpdateStatus(str, Enum):
    """Normalized update-discovery status for one managed service."""

    CURRENT = "current"
    UPDATE_AVAILABLE = "update-available"
    MUTABLE_TAG = "mutable-tag"
    UNKNOWN = "unknown"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class ImageReference:
    """Normalized container-image identity used by update discovery."""

    repository: str
    tag: str | None = None
    digest: str | None = None
    raw_reference: str | None = None

    def __post_init__(self) -> None:
        repository = _required_repository(self.repository)
        tag = _optional_tag(self.tag)
        digest = _optional_digest(self.digest)

        raw_reference = self.raw_reference
        if raw_reference is None:
            raw_reference = _compose_reference(
                repository=repository,
                tag=tag,
                digest=digest,
            )
        else:
            raw_reference = _required_text(
                raw_reference,
                "raw_reference",
            )

        object.__setattr__(self, "repository", repository)
        object.__setattr__(self, "tag", tag)
        object.__setattr__(self, "digest", digest)
        object.__setattr__(self, "raw_reference", raw_reference)

    @classmethod
    def parse(cls, value: object) -> "ImageReference":
        """Parse a Docker-compatible image reference into normalized parts."""

        raw = _required_text(value, "image reference")
        name_and_tag, digest = _split_digest(raw)
        repository, tag = _split_tag(
            name_and_tag,
            digest_present=digest is not None,
        )

        return cls(
            repository=repository,
            tag=tag,
            digest=digest,
            raw_reference=raw,
        )

    @property
    def is_mutable(self) -> bool:
        """Return whether the reference uses the conventional mutable tag."""

        return self.tag == "latest"

    @property
    def canonical_reference(self) -> str:
        """Return a normalized tag-and-digest image reference."""

        return _compose_reference(
            repository=self.repository,
            tag=self.tag,
            digest=self.digest,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized image-reference contract."""

        return {
            "repository": self.repository,
            "tag": self.tag,
            "digest": self.digest,
            "raw_reference": self.raw_reference,
            "canonical_reference": self.canonical_reference,
            "is_mutable": self.is_mutable,
        }


@dataclass(frozen=True)
class ServiceUpdate:
    """One normalized read-only update evaluation for a managed service."""

    service_identifier: str
    service_name: str
    current_image: ImageReference
    status: UpdateStatus
    available_image: ImageReference | None = None
    reason: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "service_identifier",
            _required_identifier(
                self.service_identifier,
                "service_identifier",
            ),
        )
        object.__setattr__(
            self,
            "service_name",
            _required_text(self.service_name, "service_name"),
        )

        if not isinstance(self.current_image, ImageReference):
            raise ServiceLifecycleError(
                "current_image must be an ImageReference",
            )
        if (
            self.available_image is not None
            and not isinstance(self.available_image, ImageReference)
        ):
            raise ServiceLifecycleError(
                "available_image must be an ImageReference",
            )

        object.__setattr__(
            self,
            "status",
            _normalize_enum(
                self.status,
                UpdateStatus,
                "status",
            ),
        )
        object.__setattr__(
            self,
            "reason",
            _optional_text(self.reason, "reason"),
        )

        if not isinstance(self.details, Mapping):
            raise ServiceLifecycleError("details must be an object")
        object.__setattr__(self, "details", dict(self.details))
        object.__setattr__(
            self,
            "evaluated_at",
            _required_timestamp(self.evaluated_at, "evaluated_at"),
        )

        if (
            self.status is UpdateStatus.UPDATE_AVAILABLE
            and self.available_image is None
        ):
            raise ServiceLifecycleError(
                "available_image is required when an update is available",
            )

    @property
    def requires_attention(self) -> bool:
        """Return whether the update state merits administrator attention."""

        return self.status in {
            UpdateStatus.UPDATE_AVAILABLE,
            UpdateStatus.MUTABLE_TAG,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized service-update contract."""

        return {
            "service_identifier": self.service_identifier,
            "service_name": self.service_name,
            "status": self.status.value,
            "requires_attention": self.requires_attention,
            "current_image": self.current_image.to_dict(),
            "available_image": (
                self.available_image.to_dict()
                if self.available_image is not None
                else None
            ),
            "reason": self.reason,
            "details": dict(self.details),
            "evaluated_at": self.evaluated_at,
        }


@dataclass(frozen=True)
class UpdateReport:
    """Normalized read-only update-discovery report."""

    updates: tuple[ServiceUpdate, ...] = ()
    provider: str = "unknown"
    evaluated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "updates",
            _normalize_updates(self.updates),
        )
        object.__setattr__(
            self,
            "provider",
            _required_identifier(self.provider, "provider"),
        )
        object.__setattr__(
            self,
            "evaluated_at",
            _required_timestamp(self.evaluated_at, "evaluated_at"),
        )

        identifiers = tuple(
            update.service_identifier
            for update in self.updates
        )
        if len(identifiers) != len(set(identifiers)):
            raise ServiceLifecycleError(
                "service updates must have unique service identifiers",
            )

    @property
    def status(self) -> str:
        """Return the normalized aggregate update-report status."""

        statuses = {update.status for update in self.updates}
        if UpdateStatus.UPDATE_AVAILABLE in statuses:
            return "updates-available"
        if UpdateStatus.MUTABLE_TAG in statuses:
            return "attention"
        if statuses & {UpdateStatus.UNKNOWN, UpdateStatus.UNSUPPORTED}:
            return "incomplete"
        return "current"

    @property
    def requires_attention(self) -> bool:
        """Return whether any service update requires administrator attention."""

        return any(update.requires_attention for update in self.updates)

    @property
    def counts(self) -> dict[str, int]:
        """Return deterministic update counts by normalized status."""

        counts = {
            status.value: 0
            for status in UpdateStatus
        }
        for update in self.updates:
            counts[update.status.value] += 1
        return counts

    @property
    def attention(self) -> tuple[ServiceUpdate, ...]:
        """Return update evaluations requiring administrator attention."""

        return tuple(
            update
            for update in self.updates
            if update.requires_attention
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized update-discovery report."""

        return {
            "status": self.status,
            "provider": self.provider,
            "total_services": len(self.updates),
            "counts": self.counts,
            "requires_attention": self.requires_attention,
            "attention": [
                update.to_dict()
                for update in self.attention
            ],
            "updates": [
                update.to_dict()
                for update in self.updates
            ],
            "evaluated_at": self.evaluated_at,
        }


def _split_digest(value: str) -> tuple[str, str | None]:
    if "@" not in value:
        return value, None

    name_and_tag, digest = value.rsplit("@", 1)
    if not name_and_tag:
        raise ServiceLifecycleError(
            "image reference repository must be non-empty",
        )
    return name_and_tag, _optional_digest(digest)


def _split_tag(
    value: str,
    *,
    digest_present: bool = False,
) -> tuple[str, str | None]:
    last_slash = value.rfind("/")
    last_colon = value.rfind(":")

    if last_colon > last_slash:
        repository = value[:last_colon]
        tag = value[last_colon + 1 :]
    else:
        repository = value
        tag = None if digest_present else "latest"

    return _required_repository(repository), _optional_tag(tag)

def _compose_reference(
    *,
    repository: str,
    tag: str | None,
    digest: str | None,
) -> str:
    reference = repository
    if tag is not None:
        reference = f"{reference}:{tag}"
    if digest is not None:
        reference = f"{reference}@{digest}"
    return reference


def _normalize_updates(value: object) -> tuple[ServiceUpdate, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ServiceLifecycleError(
            "updates must be a collection of ServiceUpdate objects",
        )

    updates = tuple(value)
    if any(not isinstance(item, ServiceUpdate) for item in updates):
        raise ServiceLifecycleError(
            "updates must contain ServiceUpdate objects",
        )

    return tuple(
        sorted(
            updates,
            key=lambda update: (
                _status_rank(update.status),
                update.service_identifier,
            ),
        )
    )


def _status_rank(status: UpdateStatus) -> int:
    return {
        UpdateStatus.UPDATE_AVAILABLE: 0,
        UpdateStatus.MUTABLE_TAG: 1,
        UpdateStatus.UNKNOWN: 2,
        UpdateStatus.UNSUPPORTED: 3,
        UpdateStatus.CURRENT: 4,
    }[status]


def _normalize_enum(
    value: object,
    enum_type: type[Enum],
    field_name: str,
) -> Enum:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be non-empty text",
        )

    normalized = value.strip().casefold()
    try:
        return enum_type(normalized)
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"invalid {field_name}: {normalized}",
        ) from exc


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be non-empty text",
        )
    return value.strip()


def _optional_text(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name)


def _required_identifier(value: object, field_name: str) -> str:
    normalized = _required_text(value, field_name).casefold()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ServiceLifecycleError(
            f"invalid {field_name}: {normalized}",
        )
    return normalized


def _required_repository(value: object) -> str:
    repository = _required_text(value, "repository").casefold()
    if (
        repository.startswith("/")
        or repository.endswith("/")
        or any(character.isspace() for character in repository)
        or "@" in repository
    ):
        raise ServiceLifecycleError(
            f"invalid repository: {repository}",
        )
    return repository


def _optional_tag(value: object) -> str | None:
    if value is None:
        return None

    tag = _required_text(value, "tag")
    if (
        tag.startswith(".")
        or tag.startswith("-")
        or len(tag) > 128
        or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", tag)
    ):
        raise ServiceLifecycleError(f"invalid tag: {tag}")
    return tag


def _optional_digest(value: object) -> str | None:
    if value is None:
        return None

    digest = _required_text(value, "digest").casefold()
    if not _DIGEST_PATTERN.fullmatch(digest):
        raise ServiceLifecycleError(f"invalid digest: {digest}")
    return digest


def _required_timestamp(value: object, field_name: str) -> str:
    normalized = _required_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise ServiceLifecycleError(
            f"{field_name} must include a timezone",
        )

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
