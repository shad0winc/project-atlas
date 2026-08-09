"""Durable media-request repository for Project Atlas."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import re
from typing import Any

from atlas.atomic import write_json_atomic

from .models import (
    MediaRequest,
    MediaRequestError,
    MediaRequestType,
)


SCHEMA_VERSION = 1
_REQUEST_IDENTIFIER_PATTERN = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?$",
)
_PROVIDER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


class MediaRequestRepositoryError(ValueError):
    """Raised when media-request persistence cannot be completed safely."""


class MediaRequestRepositoryConflictError(
    MediaRequestRepositoryError
):
    """Raised when an active request already owns the provider target."""


class JsonMediaRequestRepository:
    """Persist normalized media requests in one atomic JSON registry."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.registry_file = self.root / "requests.json"
        self.lock_file = self.root / "requests.lock"

    def initialize(self) -> None:
        """Create the repository layout when it does not already exist."""

        self.root.mkdir(parents=True, exist_ok=True)

        if self.registry_file.exists():
            return

        with self._exclusive_lock():
            if not self.registry_file.exists():
                self._write_document(
                    self._empty_document(),
                )

    def save(self, request: MediaRequest) -> MediaRequest:
        """Persist one new request and reject duplicate identities."""

        return self._save(
            request,
            reject_active_target_conflict=False,
        )

    def save_if_no_active_conflict(
        self,
        request: MediaRequest,
    ) -> MediaRequest:
        """Persist a request only when no active provider target overlaps."""

        return self._save(
            request,
            reject_active_target_conflict=True,
        )

    def _save(
        self,
        request: MediaRequest,
        *,
        reject_active_target_conflict: bool,
    ) -> MediaRequest:
        if not isinstance(request, MediaRequest):
            raise MediaRequestRepositoryError(
                "request must be a MediaRequest",
            )

        self.initialize()

        with self._exclusive_lock():
            document = self._load_document_initialized()
            requests = dict(document["requests"])

            if request.request_id in requests:
                raise MediaRequestRepositoryError(
                    f"media request already exists: {request.request_id}",
                )

            if request.provider_request_id is not None:
                duplicate = self._find_provider_request_in_records(
                    requests,
                    request.provider,
                    request.provider_request_id,
                )
                if duplicate is not None:
                    raise MediaRequestRepositoryError(
                        "provider request already exists: "
                        f"{request.provider}:{request.provider_request_id}",
                    )

            if reject_active_target_conflict:
                conflict = self._find_active_target_conflict_in_records(
                    requests,
                    request,
                )
                if conflict is not None:
                    raise MediaRequestRepositoryConflictError(
                        "active media request conflicts with provider target: "
                        f"{conflict.request_id}",
                    )

            requests[request.request_id] = request.to_dict()
            self._write_document(
                self._document(requests),
            )

        return request

    def replace(self, request: MediaRequest) -> MediaRequest:
        """Atomically replace one existing request."""

        if not isinstance(request, MediaRequest):
            raise MediaRequestRepositoryError(
                "request must be a MediaRequest",
            )

        self.initialize()

        with self._exclusive_lock():
            document = self._load_document_initialized()
            requests = dict(document["requests"])

            if request.request_id not in requests:
                raise MediaRequestRepositoryError(
                    f"media request not found: {request.request_id}",
                )

            if request.provider_request_id is not None:
                duplicate = self._find_provider_request_in_records(
                    requests,
                    request.provider,
                    request.provider_request_id,
                    exclude_request_id=request.request_id,
                )
                if duplicate is not None:
                    raise MediaRequestRepositoryError(
                        "provider request already exists: "
                        f"{request.provider}:{request.provider_request_id}",
                    )

            requests[request.request_id] = request.to_dict()

            self._write_document(
                self._document(requests),
            )

        return request

    def get(self, request_id: object) -> MediaRequest:
        """Return one request by normalized request identity."""

        normalized_id = _required_identity(
            request_id,
            "request_id",
        )
        document = self._load_document()
        payload = document["requests"].get(normalized_id)

        if payload is None:
            raise MediaRequestRepositoryError(
                f"media request not found: {normalized_id}",
            )

        return self._request_from_payload(
            payload,
            expected_request_id=normalized_id,
        )

    def list(self) -> tuple[MediaRequest, ...]:
        """Return all requests in deterministic chronological order."""

        document = self._load_document()
        requests = tuple(
            self._request_from_payload(
                payload,
                expected_request_id=request_id,
            )
            for request_id, payload in document["requests"].items()
        )

        return tuple(
            sorted(
                requests,
                key=lambda request: (
                    request.created_at,
                    request.request_id,
                ),
            )
        )

    def list_by_user(
        self,
        user_id: object,
    ) -> tuple[MediaRequest, ...]:
        """Return requests owned by one normalized Atlas user."""

        normalized_user_id = _required_identity(
            user_id,
            "user_id",
        )

        return tuple(
            request
            for request in self.list()
            if request.user_id == normalized_user_id
        )

    def find_by_provider_request(
        self,
        provider: object,
        provider_request_id: object,
    ) -> MediaRequest | None:
        """Return a request by provider and provider-side request identity."""

        normalized_provider = _required_provider(
            provider,
            "provider",
        )
        normalized_provider_request_id = _required_identity(
            provider_request_id,
            "provider_request_id",
        )

        for request in self.list():
            if (
                request.provider == normalized_provider
                and request.provider_request_id
                == normalized_provider_request_id
            ):
                return request

        return None

    def delete(self, request_id: object) -> MediaRequest:
        """Delete and return one persisted request."""

        normalized_id = _required_identity(
            request_id,
            "request_id",
        )
        self.initialize()

        with self._exclusive_lock():
            document = self._load_document_initialized()
            requests = dict(document["requests"])
            payload = requests.get(normalized_id)

            if payload is None:
                raise MediaRequestRepositoryError(
                    f"media request not found: {normalized_id}",
                )

            request = self._request_from_payload(
                payload,
                expected_request_id=normalized_id,
            )
            del requests[normalized_id]

            self._write_document(
                self._document(requests),
            )

        return request

    def _write_document(
        self,
        document: Mapping[str, Any],
    ) -> None:
        try:
            write_json_atomic(
                self.registry_file,
                document,
            )
        except OSError as exc:
            raise MediaRequestRepositoryError(
                "unable to persist media-request registry: "
                f"{self.registry_file}",
            ) from exc

    def _load_document(self) -> dict[str, Any]:
        self.initialize()
        return self._load_document_initialized()

    def _load_document_initialized(self) -> dict[str, Any]:
        try:
            raw = self.registry_file.read_text(encoding="utf-8")
        except OSError as exc:
            raise MediaRequestRepositoryError(
                f"unable to read media-request registry: {self.registry_file}",
            ) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MediaRequestRepositoryError(
                f"media-request registry contains invalid JSON: "
                f"{self.registry_file}",
            ) from exc

        if not isinstance(payload, Mapping):
            raise MediaRequestRepositoryError(
                "media-request registry must be an object",
            )

        if payload.get("schema_version") != SCHEMA_VERSION:
            raise MediaRequestRepositoryError(
                "unsupported media-request registry schema_version",
            )

        requests = payload.get("requests")
        if not isinstance(requests, Mapping):
            raise MediaRequestRepositoryError(
                "media-request registry requests must be an object",
            )

        normalized_requests: dict[str, Mapping[str, Any]] = {}

        for raw_request_id, record in requests.items():
            request_id = _required_identity(
                raw_request_id,
                "registry request_id",
            )

            if not isinstance(record, Mapping):
                raise MediaRequestRepositoryError(
                    f"media-request record must be an object: {request_id}",
                )

            normalized_requests[request_id] = record

        return {
            "schema_version": SCHEMA_VERSION,
            "requests": normalized_requests,
        }

    def _request_from_payload(
        self,
        payload: Mapping[str, Any],
        *,
        expected_request_id: str,
    ) -> MediaRequest:
        fields = {
            "request_id": payload.get("request_id"),
            "user_id": payload.get("user_id"),
            "media_type": payload.get("media_type"),
            "provider": payload.get("provider"),
            "provider_request_id": payload.get(
                "provider_request_id",
            ),
            "provider_media_id": payload.get("provider_media_id"),
            "title": payload.get("title"),
            "year": payload.get("year"),
            "season_number": payload.get("season_number"),
            "status": payload.get("status"),
            "created_at": payload.get("created_at"),
            "updated_at": payload.get("updated_at"),
            "available_at": payload.get("available_at"),
        }

        try:
            request = MediaRequest(**fields)
        except (MediaRequestError, TypeError) as exc:
            raise MediaRequestRepositoryError(
                f"invalid media-request record: {expected_request_id}",
            ) from exc

        if request.request_id != expected_request_id:
            raise MediaRequestRepositoryError(
                "media-request registry key does not match record request_id: "
                f"{expected_request_id}",
            )

        expected_derived = {
            "terminal": request.terminal,
            "active": request.active,
        }
        for field_name, expected in expected_derived.items():
            if (
                field_name in payload
                and payload[field_name] is not expected
            ):
                raise MediaRequestRepositoryError(
                    f"media-request derived field does not match: "
                    f"{expected_request_id}.{field_name}",
                )

        return request

    def _find_provider_request_in_records(
        self,
        records: Mapping[str, Mapping[str, Any]],
        provider: str,
        provider_request_id: str,
        *,
        exclude_request_id: str | None = None,
    ) -> MediaRequest | None:
        for request_id, payload in records.items():
            if request_id == exclude_request_id:
                continue
            request = self._request_from_payload(
                payload,
                expected_request_id=request_id,
            )
            if (
                request.provider == provider
                and request.provider_request_id
                == provider_request_id
            ):
                return request

        return None

    def _find_active_target_conflict_in_records(
        self,
        records: Mapping[str, Mapping[str, Any]],
        candidate: MediaRequest,
    ) -> MediaRequest | None:
        for request_id, payload in records.items():
            request = self._request_from_payload(
                payload,
                expected_request_id=request_id,
            )

            if (
                request.active
                and _request_targets_overlap(
                    request,
                    candidate,
                )
            ):
                return request

        return None

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

        try:
            handle = self.lock_file.open(
                "a+",
                encoding="utf-8",
            )
        except OSError as exc:
            raise MediaRequestRepositoryError(
                "unable to open media-request lock file: "
                f"{self.lock_file}",
            ) from exc

        try:
            try:
                fcntl.flock(
                    handle.fileno(),
                    fcntl.LOCK_EX,
                )
            except OSError as exc:
                raise MediaRequestRepositoryError(
                    "unable to acquire media-request lock: "
                    f"{self.lock_file}",
                ) from exc

            try:
                yield
            finally:
                try:
                    fcntl.flock(
                        handle.fileno(),
                        fcntl.LOCK_UN,
                    )
                except OSError as exc:
                    raise MediaRequestRepositoryError(
                        "unable to release media-request lock: "
                        f"{self.lock_file}",
                    ) from exc
        finally:
            handle.close()

    @staticmethod
    def _empty_document() -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "requests": {},
        }

    @staticmethod
    def _document(
        requests: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "requests": {
                request_id: requests[request_id]
                for request_id in sorted(requests)
            },
        }


def _request_targets_overlap(
    existing: MediaRequest,
    candidate: MediaRequest,
) -> bool:
    if existing.provider != candidate.provider:
        return False

    if existing.provider_media_id != candidate.provider_media_id:
        return False

    existing_family = _provider_media_family(existing)
    candidate_family = _provider_media_family(candidate)

    if existing_family != candidate_family:
        return False

    if (
        existing.media_type in {
            MediaRequestType.TV,
            MediaRequestType.ANIME_TV,
        }
        and candidate.media_type in {
            MediaRequestType.TV,
            MediaRequestType.ANIME_TV,
        }
    ):
        return (
            existing.season_number is None
            or candidate.season_number is None
            or existing.season_number == candidate.season_number
        )

    return True


def _provider_media_family(
    request: MediaRequest,
) -> str:
    if request.provider == "jellyseerr":
        if request.media_type in {
            MediaRequestType.MOVIE,
            MediaRequestType.ANIME_MOVIE,
        }:
            return "movie"

        if request.media_type in {
            MediaRequestType.TV,
            MediaRequestType.ANIME_TV,
        }:
            return "tv"

    return request.media_type.value


def _required_identity(
    value: object,
    field_name: str,
) -> str:
    if isinstance(value, bool):
        raise MediaRequestRepositoryError(
            f"{field_name} must be text or an integer",
        )

    if isinstance(value, int):
        normalized = str(value)
    elif isinstance(value, str):
        normalized = value.strip()
    else:
        raise MediaRequestRepositoryError(
            f"{field_name} must be text or an integer",
        )

    if (
        not normalized
        or not _REQUEST_IDENTIFIER_PATTERN.fullmatch(normalized)
    ):
        raise MediaRequestRepositoryError(
            f"{field_name} is invalid",
        )

    return normalized


def _required_provider(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise MediaRequestRepositoryError(
            f"{field_name} must be text",
        )

    normalized = value.strip().lower().replace(" ", "-")

    if (
        not normalized
        or not _PROVIDER_PATTERN.fullmatch(normalized)
    ):
        raise MediaRequestRepositoryError(
            f"{field_name} is invalid",
        )

    return normalized
