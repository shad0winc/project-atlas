"""Shared request consumers; persisted schema selects compatibility, not migration.

Missing state retains schema 1. Schema 2 must already have been explicitly
migrated by an operator; construction never creates or rewrites a registry.
This boundary does not activate acquisition routing, recovery jobs or profiles.
"""

from __future__ import annotations

from collections.abc import Iterable
import json
import os
from pathlib import Path
import stat

from .provider import MediaRequestProvider
from .repository import JsonMediaRequestRepository, MediaRequestRepositoryError
from .service import EventPublisher, MediaRequestService
from .submission_recovery import SubmissionRecoveryRepository, SubmissionRecoveryService
from .submission_events import SubmissionEventJournalPublisher


def open_request_repository(root: str | Path) -> JsonMediaRequestRepository:
    """Select the persisted contract without initialization or external work."""
    registry = Path(root) / "requests.json"
    try:
        descriptor = os.open(registry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return JsonMediaRequestRepository(root)
    except OSError:
        raise MediaRequestRepositoryError("Request registry could not be inspected") from None

    try:
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError("Not a regular registry")
            document = json.load(handle)
        if not isinstance(document, dict) or not isinstance(document.get("requests"), dict):
            raise ValueError("Invalid registry shape")
        schema = document.get("schema_version")
        if type(schema) is not int or schema not in (1, 2):
            raise ValueError("Unsupported registry schema")
        if schema == 1 and {"submissions", "submission_outbox"} & document.keys():
            raise ValueError("Recovery journals require schema 2")
        repository = (
            SubmissionRecoveryRepository(root)
            if schema == 2 else JsonMediaRequestRepository(root)
        )
        # Validate recovery journals before exposing a schema-2 consumer.
        # Normal request records are validated by the repository on access.
        repository._extra_fields(document)
        return repository
    except (OSError, ValueError, TypeError):
        raise MediaRequestRepositoryError("Request registry contract is invalid") from None


def build_request_service(
    repository: JsonMediaRequestRepository,
    providers: Iterable[MediaRequestProvider],
    *,
    event_publisher: EventPublisher | None = None,
) -> MediaRequestService:
    """Pair every consumer with the service required by its repository."""
    if isinstance(repository, SubmissionRecoveryRepository):
        return SubmissionRecoveryService(
            repository, providers, event_publisher=event_publisher,
            submission_event_publisher=SubmissionEventJournalPublisher.from_environment().publish,
        )
    return MediaRequestService(repository, providers, event_publisher=event_publisher)
