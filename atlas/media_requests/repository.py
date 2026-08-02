"""Durable media-request repository for Project Atlas."""

from __future__ import annotations

from collections.abc import Mapping
import json
from pathlib import Path
import re
from typing import Any

from atlas.atomic import write_json_atomic

from .models import (
    MediaRequest,
    MediaRequestError,
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


class JsonMediaRequestRepository:
    """Persist normalized media requests in one atomic JSON registry."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.registry_file = self.root / "requests.json"

    def initialize(self) -> None:
        """Create the repository layout when it does not already exist."""

        self.root.mkdir(parents=True, exist_ok=True)

        if not self.registry_file.exists():
            write_json_atomic(
                self.registry_file,
                self._empty_document(),
            )

    def save(self, request: MediaRequest) -> MediaRequest:
        """Persist one new request and reject duplicate identities."""

        if not isinstance(request, MediaRequest):
            raise MediaRequestRepositoryError(
                "request must be a MediaRequest",
            )

        document = self._load_document()
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

        requests[request.request_id] = request.to_dict()
        write_json_atomic(
            self.registry_file,
            self._document(requests),
        )

        return request

    def replace(self, request: MediaRequest) -> MediaRequest:
        """Atomically replace one existing request."""

        if not isinstance(request, MediaRequest):
            raise MediaRequestRepositoryError(
                "request must be a MediaRequest",
            )

        document = self._load_document()
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

        write_json_atomic(
            self.registry_file,
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
        document = self._load_document()
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

        write_json_atomic(
            self.registry_file,
            self._document(requests),
        )

        return request

    def _load_document(self) -> dict[str, Any]:
        self.initialize()

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
