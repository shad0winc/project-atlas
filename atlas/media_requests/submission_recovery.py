"""Opt-in durable submission receipts; legacy repositories remain schema 1.

Schema 2 requires an explicit operator migration and recovery-aware callers.
Importing this module does not enable it in any default factory.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping
from uuid import uuid4

from .events import MediaRequestEvent, MediaRequestEventType, event_type_for_status
from .models import MediaRequest, MediaRequestStatus
from .provider import MediaRequestProviderError, ProviderStatusResult
from .repository import (
    JsonMediaRequestRepository, MediaRequestRepositoryError,
    MediaRequestRepositoryConflictError,
)
from .service import MediaRequestService, MediaRequestServiceError
from .providers.jellyseerr import JellyseerrMediaRequestProvider
from .providers.managed_profiles import positive_id, server_id


def _fingerprint(request: MediaRequest) -> str:
    fields = request.to_dict()
    for key in ("status", "updated_at", "available_at", "provider_request_id", "active", "terminal"):
        fields.pop(key, None)
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class SubmissionAttempt:
    attempt_id: str
    request_id: str
    fingerprint: str
    server_id: int
    profile_id: int
    started_at: str
    receipt_id: int | None = None
    revision: int = 0
    phase: str = "POST_STARTED"

    def __post_init__(self):
        if (not isinstance(self.attempt_id, str) or re.fullmatch(r"[a-f0-9]{32}", self.attempt_id) is None
                or not isinstance(self.request_id, str) or not self.request_id
                or re.fullmatch(r"[a-f0-9]{64}", self.fingerprint) is None):
            raise MediaRequestRepositoryError("Submission attempt identity is invalid")
        server_id(self.server_id)
        positive_id(self.profile_id)
        if self.receipt_id is not None:
            positive_id(self.receipt_id)
        if type(self.revision) is not int or self.revision < 0:
            raise MediaRequestRepositoryError("Submission attempt revision is invalid")
        stamp = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise MediaRequestRepositoryError("Submission attempt timestamp is invalid")
        if self.phase not in {"POST_STARTED", "RECEIPT_OBSERVED", "BOUND"}:
            raise MediaRequestRepositoryError("Submission attempt phase is invalid")
        if (self.phase == "POST_STARTED") != (self.receipt_id is None):
            raise MediaRequestRepositoryError("Submission receipt phase is inconsistent")

    def to_dict(self):
        return dict(self.__dict__)


class SubmissionRecoveryRepository(JsonMediaRequestRepository):
    """Request, attempt and submission outbox share one fsynced transaction."""
    schema_version = 2

    def _empty_document(self):
        return dict(schema_version=2, requests={}, submissions={}, submission_outbox={})

    def _extra_fields(self, payload):
        if payload and not {"submissions", "submission_outbox"} <= set(payload):
            raise MediaRequestRepositoryError("Submission journal fields are missing")
        attempts = payload.get("submissions", {})
        outbox = payload.get("submission_outbox", {})
        if not isinstance(attempts, Mapping) or not isinstance(outbox, Mapping):
            raise MediaRequestRepositoryError("Submission journal is invalid")
        for key, raw in attempts.items():
            try:
                row = SubmissionAttempt(**raw)
                if key != row.request_id:
                    raise ValueError("Mismatched journal key")
                request_raw = payload.get("requests", {}).get(key)
                if request_raw is None:
                    raise ValueError("Orphaned attempt")
                request = self._request_from_payload(request_raw, expected_request_id=key)
                if _fingerprint(request) != row.fingerprint:
                    raise ValueError("Changed intent")
                if row.phase == "BOUND":
                    if request.provider_request_id != str(row.receipt_id) or request.status is MediaRequestStatus.SUBMITTING:
                        raise ValueError("Conflicting bound owner")
                elif request.status is not MediaRequestStatus.SUBMITTING or request.provider_request_id is not None:
                    raise ValueError("Missing mutation barrier")
            except Exception:
                raise MediaRequestRepositoryError("Submission journal is invalid") from None
        for key, raw in outbox.items():
            if (not isinstance(raw, dict) or set(raw) != {"event", "payload", "delivered"}
                    or type(raw["delivered"]) is not bool or not isinstance(raw["payload"], dict)
                    or raw["event"] not in {v.value for v in MediaRequestEventType}
                    or not isinstance(raw["payload"].get("metadata"), dict)
                    or raw["payload"]["metadata"].get("submission_event_id") != key):
                raise MediaRequestRepositoryError("Submission outbox is invalid")
        return dict(submissions=dict(attempts), submission_outbox=dict(outbox))

    def _write_document(self, document):
        # Base helper is rename-atomic but not fsync-durable. Receipts need both.
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            if self.registry_file.is_symlink():
                raise OSError("Recovery registry cannot be a symlink")
            original = self.registry_file.stat() if self.registry_file.exists() else None
            fd, name = tempfile.mkstemp(prefix=".requests-recovery-", dir=self.root)
            temporary = Path(name)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                if original is not None:
                    os.fchmod(handle.fileno(), original.st_mode & 0o777)
                    os.fchown(handle.fileno(), original.st_uid, original.st_gid)
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.registry_file)
            directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            raise MediaRequestRepositoryError("Submission transaction could not be persisted") from None
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _current(self, document, expected):
        raw = document["requests"].get(expected.request_id)
        if raw is None:
            raise MediaRequestRepositoryConflictError("Submission request is missing")
        current = self._request_from_payload(raw, expected_request_id=expected.request_id)
        if current != expected:
            raise MediaRequestRepositoryConflictError("Submission request changed during operation")
        return current

    def begin_submission(self, expected, *, server, profile, started_at):
        self.initialize()
        with self._exclusive_lock():
            document = self._load_document_initialized()
            self._current(document, expected)
            if (expected.status is not MediaRequestStatus.PENDING or expected.provider_request_id is not None
                    or expected.request_id in document["submissions"]):
                raise MediaRequestRepositoryConflictError("Submission attempt already exists or is blocked")
            intent = replace(expected, status=MediaRequestStatus.SUBMITTING)
            attempt = SubmissionAttempt(uuid4().hex, intent.request_id, _fingerprint(intent),
                                        server, profile, started_at)
            document["requests"][intent.request_id] = intent.to_dict()
            document["submissions"][intent.request_id] = attempt.to_dict()
            self._write_document(document)
            return intent, attempt

    def get_attempt(self, request_id):
        raw = self._load_document()["submissions"].get(request_id)
        return None if raw is None else SubmissionAttempt(**raw)

    def observe_receipt(self, expected, attempt, receipt_id):
        positive_id(receipt_id)
        with self._exclusive_lock():
            document = self._load_document_initialized()
            self._current(document, expected)
            current = SubmissionAttempt(**document["submissions"][expected.request_id])
            if current.receipt_id == receipt_id and current.attempt_id == attempt.attempt_id:
                return current
            if current != attempt or current.phase != "POST_STARTED":
                raise MediaRequestRepositoryConflictError("Submission receipt cannot be overwritten")
            for key, raw in document["submissions"].items():
                if key != expected.request_id and raw["receipt_id"] == receipt_id:
                    raise MediaRequestRepositoryConflictError("Submission receipt already has an owner")
            if self._find_provider_request_in_records(document["requests"], expected.provider, str(receipt_id)):
                raise MediaRequestRepositoryConflictError("Submission receipt already has a bound owner")
            observed = replace(current, receipt_id=receipt_id, phase="RECEIPT_OBSERVED", revision=current.revision + 1)
            document["submissions"][expected.request_id] = observed.to_dict()
            self._write_document(document)
            return observed

    @classmethod
    def migrate_from_v1(cls, root, *, expected_sha256, backup_file):
        """Explicit offline migration. No default caller invokes this method.

        All readers/writers must be paused and their schema-2 wiring reviewed
        before the operator uses this method. Rollback requires the snapshot
        and reconciliation of any later external attempts; never overlay a
        pre-attempt backup over an active journal.
        """
        root = Path(root)
        backup_file = Path(backup_file)
        if not root.is_dir() or backup_file == root / "requests.json":
            raise MediaRequestRepositoryError("Migration paths are invalid")
        if not isinstance(expected_sha256, str) or re.fullmatch(r"[a-f0-9]{64}", expected_sha256) is None:
            raise MediaRequestRepositoryError("Migration baseline hash is invalid")
        old = JsonMediaRequestRepository(root)
        new = cls(root)
        with old._exclusive_lock():
            if old.registry_file.is_symlink() or not old.registry_file.is_file():
                raise MediaRequestRepositoryError("Migration registry must be a regular file")
            raw = old.registry_file.read_bytes()
            if hashlib.sha256(raw).hexdigest() != expected_sha256:
                raise MediaRequestRepositoryConflictError("Migration registry changed")
            original = json.loads(raw)
            if set(original) != {"schema_version", "requests"} or type(original["schema_version"]) is not int:
                raise MediaRequestRepositoryError("Migration registry shape is unsupported")
            document = old._load_document_initialized()
            for key, record in document["requests"].items():
                old._request_from_payload(record, expected_request_id=key)
            # Backup is exclusive and durable before replacing the live document.
            try:
                fd = os.open(backup_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                directory = os.open(backup_file.parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            except OSError:
                raise MediaRequestRepositoryError("Migration backup could not be persisted") from None
            migrated = dict(schema_version=2, requests=document["requests"], submissions={}, submission_outbox={})
            new._write_document(migrated)
        return new

    def bind_submission(self, expected, attempt, result, *, occurred_at):
        with self._exclusive_lock():
            document = self._load_document_initialized()
            current = self._request_from_payload(document["requests"][expected.request_id], expected_request_id=expected.request_id)
            actual = SubmissionAttempt(**document["submissions"][expected.request_id])
            if actual.phase == "BOUND" and actual.attempt_id == attempt.attempt_id and current.provider_request_id == str(attempt.receipt_id):
                return current
            self._current(document, expected)
            if (actual != attempt or actual.phase != "RECEIPT_OBSERVED"
                    or _fingerprint(expected) != actual.fingerprint
                    or expected.status is not MediaRequestStatus.SUBMITTING
                    or result.provider != expected.provider
                    or result.provider_request_id != str(attempt.receipt_id)):
                raise MediaRequestRepositoryConflictError("Submission binding evidence changed")
            if self._find_provider_request_in_records(document["requests"], expected.provider, result.provider_request_id):
                raise MediaRequestRepositoryConflictError("Submission backend identity already has an owner")
            bound = replace(expected, provider_request_id=result.provider_request_id, status=result.status,
                            updated_at=result.updated_at, available_at=result.available_at)
            document["requests"][bound.request_id] = bound.to_dict()
            document["submissions"][bound.request_id] = replace(actual, phase="BOUND", revision=actual.revision + 1).to_dict()
            for event_type in (MediaRequestEventType.SUBMITTED, event_type_for_status(bound.status)):
                event_id = actual.attempt_id + ":" + event_type.value
                event = MediaRequestEvent.from_request(event_type, bound, occurred_at=occurred_at,
                    context=result.context, metadata={"submission_event_id": event_id})
                document["submission_outbox"][event_id] = {**event.to_dict(), "delivered": False}
            self._write_document(document)
            return bound

    def pending_submission_events(self):
        return {key: raw for key, raw in self._load_document()["submission_outbox"].items() if not raw["delivered"]}

    def acknowledge_submission_event(self, event_id):
        with self._exclusive_lock():
            document = self._load_document_initialized()
            if event_id not in document["submission_outbox"]:
                raise MediaRequestRepositoryError("Unknown submission event")
            document["submission_outbox"][event_id]["delivered"] = True
            self._write_document(document)

    def _validate_replace(self, document, current, request, expected):
        if expected is None:
            raise MediaRequestRepositoryConflictError("Recovery registry writes require expected-record guards")
        attempt = document["submissions"].get(current.request_id)
        if attempt is not None:
            if current.status is MediaRequestStatus.SUBMITTING or _fingerprint(current) != _fingerprint(request):
                raise MediaRequestRepositoryConflictError("Submission intent cannot be overwritten")

    def _validate_delete(self, document, request):
        if request.request_id in document["submissions"]:
            raise MediaRequestRepositoryConflictError("Submission journal must be retained for audit")


class SubmissionRecoveryService(MediaRequestService):
    """Opt-in acquisition service. Uncertain receipt-free attempts stay blocked."""

    def __init__(self, repository, providers, **kwargs):
        if not isinstance(repository, SubmissionRecoveryRepository):
            raise MediaRequestServiceError("Submission recovery requires its versioned repository")
        super().__init__(repository, providers, **kwargs)

    def submit_request(self, request_id):
        request = self.get_request(request_id)
        if request.audio_preference is None:
            return super().submit_request(request_id)
        provider = self._provider_for(request.provider)
        if not isinstance(provider, JellyseerrMediaRequestProvider):
            raise MediaRequestServiceError("Receipt recovery is only supported for Seerr acquisition")
        if request.status is not MediaRequestStatus.PENDING or request.provider_request_id is not None:
            raise MediaRequestServiceError("Submission requires recovery; it cannot be retried")
        # All-season expansion must be proven against native Seerr before support.
        if request.media_type.value in {"tv", "anime_tv"} and request.season_number is None:
            raise MediaRequestServiceError("All-season acquisition recovery scope is not verified")
        self._validate_submission(provider, request)
        try:
            intent, attempt = self.repository.begin_submission(request,
                server=provider._server_id_for(request.media_type), profile=provider._audio_profile_id(request),
                started_at=self._occurred_at().isoformat().replace("+00:00", "Z"))
            provider.submit_with_receipt(intent,
                lambda receipt_id: self.repository.observe_receipt(intent, attempt, receipt_id))
        except Exception:
            # A stored attempt is not rolled back, even when the POST outcome is unknown.
            raise MediaRequestServiceError("Submission remains pending verification or correlation") from None
        return self.recover_submission(request_id)

    def recover_submission(self, request_id):
        request = self.get_request(request_id)
        attempt = self.repository.get_attempt(request.request_id)
        if attempt is None:
            raise MediaRequestServiceError("Submission has no durable receipt provenance")
        if attempt.phase == "BOUND":
            if request.provider_request_id != str(attempt.receipt_id):
                raise MediaRequestServiceError("Submission binding is inconsistent")
            return request
        if request.status is not MediaRequestStatus.SUBMITTING or attempt.receipt_id is None:
            raise MediaRequestServiceError("Submission requires correlation; no automatic retry is permitted")
        if _fingerprint(request) != attempt.fingerprint:
            raise MediaRequestServiceError("Submission intent changed")
        provider = self._provider_for(request.provider)
        try:
            if (not isinstance(provider, JellyseerrMediaRequestProvider)
                    or provider._server_id_for(request.media_type) != attempt.server_id
                    or provider._audio_profile_id(request) != attempt.profile_id):
                raise ValueError("Changed routing")
            result = provider.get_recovery_status(request, attempt.receipt_id)
            self._validate_transition(request.status, result.status)
            self._validate_effective_profile(request)
            return self.repository.bind_submission(request, attempt, result, occurred_at=self._occurred_at())
        except Exception:
            raise MediaRequestServiceError("Submission receipt remains unverified") from None

    def drain_submission_events(self):
        """At-least-once delivery; consumers must deduplicate stable metadata IDs."""
        if self._event_publisher is None:
            return 0
        delivered = 0
        for event_id, event in self.repository.pending_submission_events().items():
            try:
                self._event_publisher(event["event"], event["payload"])
                self.repository.acknowledge_submission_event(event_id)
                delivered += 1
            except Exception:
                self._publication_errors.append("Submission audit delivery remains pending")
        return delivered
