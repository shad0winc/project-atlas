"""Read-only Service Lifecycle runtime snapshot provider."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..maintenance_models import (
    MaintenanceAction,
    MaintenanceRecord,
    MaintenanceReport,
    MaintenanceResult,
)
from ..models import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRuntime,
)
from ..provider import ServiceLifecycleProvider
from ..update_models import (
    ImageReference,
    ServiceUpdate,
    UpdateStatus,
)


_SCHEMA_VERSION = 1


class RuntimeSnapshotProvider(ServiceLifecycleProvider):
    """Serve normalized lifecycle observations from one JSON snapshot."""

    def __init__(
        self,
        snapshot_path: str | Path,
    ) -> None:
        if not isinstance(snapshot_path, (str, Path)):
            raise TypeError(
                "snapshot_path must be a path"
            )

        self._snapshot_path = Path(
            snapshot_path
        ).expanduser()

    def list_services(
        self,
    ) -> Sequence[ManagedService]:
        """Return managed services from the current snapshot."""

        entries = self._service_entries()

        return tuple(
            sorted(
                (
                    _parse_managed_service(
                        _mapping(
                            entry.get("service"),
                            "services[].service",
                        )
                    )
                    for entry in entries
                ),
                key=lambda service: (
                    service.name.casefold(),
                    service.identifier,
                ),
            )
        )

    def inspect_service(
        self,
        identifier: str,
    ) -> ManagedService:
        """Return one managed-service identity."""

        entry = self._entry(identifier)

        return _parse_managed_service(
            _mapping(
                entry.get("service"),
                "services[].service",
            )
        )

    def inspect_runtime(
        self,
        identifier: str,
    ) -> ServiceRuntime:
        """Return one normalized runtime observation."""

        entry = self._entry(identifier)

        return _parse_runtime(
            _mapping(
                entry.get("runtime"),
                "services[].runtime",
            )
        )

    def inspect_health(
        self,
        identifier: str,
    ) -> ServiceHealth:
        """Return one normalized health observation."""

        entry = self._entry(identifier)

        return _parse_health(
            _mapping(
                entry.get("health"),
                "services[].health",
            )
        )

    def inspect_update(
        self,
        identifier: str,
    ) -> ServiceUpdate:
        """Return one normalized update observation."""

        entry = self._entry(identifier)

        return _parse_update(
            _mapping(
                entry.get("update"),
                "services[].update",
            )
        )

    def inspect_history(
        self,
    ) -> MaintenanceReport:
        """Return normalized maintenance history."""

        payload = self._load()

        return _parse_maintenance_report(
            _mapping(
                payload.get("history"),
                "history",
            )
        )

    def inspect_service_history(
        self,
        identifier: str,
    ) -> MaintenanceReport:
        """Return maintenance history for one known service."""

        service = self.inspect_service(identifier)
        report = self.inspect_history()

        return MaintenanceReport(
            records=tuple(
                record
                for record in report.records
                if record.service_identifier
                == service.identifier
            ),
            provider=report.provider,
            generated_at=report.generated_at,
        )

    def _entry(
        self,
        identifier: str,
    ) -> Mapping[str, Any]:
        normalized = _required_text(
            identifier,
            "identifier",
        )

        for entry in self._service_entries():
            service = _mapping(
                entry.get("service"),
                "services[].service",
            )

            if service.get("identifier") == normalized:
                return entry

        raise ServiceLifecycleError(
            f"service is not present in runtime snapshot: "
            f"{normalized}"
        )

    def _service_entries(
        self,
    ) -> tuple[Mapping[str, Any], ...]:
        payload = self._load()
        services = payload.get("services")

        if not isinstance(services, list):
            raise ServiceLifecycleError(
                "runtime snapshot services must be a list"
            )

        entries: list[Mapping[str, Any]] = []

        for index, value in enumerate(services):
            entries.append(
                _mapping(
                    value,
                    f"services[{index}]",
                )
            )

        identifiers: set[str] = set()

        for entry in entries:
            service = _mapping(
                entry.get("service"),
                "services[].service",
            )
            identifier = _required_text(
                service.get("identifier"),
                "services[].service.identifier",
            )

            if identifier in identifiers:
                raise ServiceLifecycleError(
                    "runtime snapshot contains duplicate "
                    f"service identifier: {identifier}"
                )

            identifiers.add(identifier)

        return tuple(entries)

    def _load(
        self,
    ) -> Mapping[str, Any]:
        try:
            raw = self._snapshot_path.read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise ServiceLifecycleError(
                "unable to read Service Lifecycle "
                "runtime snapshot"
            ) from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ServiceLifecycleError(
                "Service Lifecycle runtime snapshot "
                "contains invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise ServiceLifecycleError(
                "Service Lifecycle runtime snapshot "
                "must be an object"
            )

        if payload.get("schema_version") != _SCHEMA_VERSION:
            raise ServiceLifecycleError(
                "unsupported Service Lifecycle runtime "
                "snapshot schema version"
            )

        _required_text(
            payload.get("generated_at"),
            "generated_at",
        )
        _required_text(
            payload.get("provider"),
            "provider",
        )

        if "services" not in payload:
            raise ServiceLifecycleError(
                "runtime snapshot services are missing"
            )

        if "history" not in payload:
            raise ServiceLifecycleError(
                "runtime snapshot history is missing"
            )

        return payload


def _parse_managed_service(
    payload: Mapping[str, Any],
) -> ManagedService:
    dependencies = payload.get(
        "dependencies",
        [],
    )

    if not isinstance(dependencies, list):
        raise ServiceLifecycleError(
            "managed service dependencies must be a list"
        )

    return ManagedService(
        identifier=_required_text(
            payload.get("identifier"),
            "service.identifier",
        ),
        name=_required_text(
            payload.get("name"),
            "service.name",
        ),
        provider=_required_text(
            payload.get("provider"),
            "service.provider",
        ),
        enabled=_required_bool(
            payload.get("enabled", True),
            "service.enabled",
        ),
        compose_project=_optional_text(
            payload.get("compose_project"),
            "service.compose_project",
        ),
        container_name=_optional_text(
            payload.get("container_name"),
            "service.container_name",
        ),
        dependencies=tuple(
            _required_text(
                value,
                "service.dependencies[]",
            )
            for value in dependencies
        ),
        created_at=_optional_text(
            payload.get("created_at"),
            "service.created_at",
        ),
        updated_at=_optional_text(
            payload.get("updated_at"),
            "service.updated_at",
        ),
    )


def _parse_service_image(
    payload: Mapping[str, Any],
) -> ServiceImage:
    return ServiceImage(
        reference=_required_text(
            payload.get("reference"),
            "runtime.image.reference",
        ),
        repository=_optional_text(
            payload.get("repository"),
            "runtime.image.repository",
        ),
        tag=_optional_text(
            payload.get("tag"),
            "runtime.image.tag",
        ),
        digest=_optional_text(
            payload.get("digest"),
            "runtime.image.digest",
        ),
        image_id=_optional_text(
            payload.get("image_id"),
            "runtime.image.image_id",
        ),
        created_at=_optional_text(
            payload.get("created_at"),
            "runtime.image.created_at",
        ),
    )


def _parse_runtime(
    payload: Mapping[str, Any],
) -> ServiceRuntime:
    image = _mapping(
        payload.get("image"),
        "runtime.image",
    )

    return ServiceRuntime(
        state=_required_text(
            payload.get("state"),
            "runtime.state",
        ),
        health=_required_text(
            payload.get("health"),
            "runtime.health",
        ),
        image=_parse_service_image(image),
        restart_count=_required_int(
            payload.get("restart_count", 0),
            "runtime.restart_count",
        ),
        started_at=_optional_text(
            payload.get("started_at"),
            "runtime.started_at",
        ),
        finished_at=_optional_text(
            payload.get("finished_at"),
            "runtime.finished_at",
        ),
        exit_code=_optional_int(
            payload.get("exit_code"),
            "runtime.exit_code",
        ),
        status_message=_optional_text(
            payload.get("status_message"),
            "runtime.status_message",
        ),
    )


def _parse_health(
    payload: Mapping[str, Any],
) -> ServiceHealth:
    warnings = _text_list(
        payload.get("warnings", []),
        "health.warnings",
    )
    errors = _text_list(
        payload.get("errors", []),
        "health.errors",
    )
    details = payload.get("details", {})

    if not isinstance(details, dict):
        raise ServiceLifecycleError(
            "health.details must be an object"
        )

    try:
        status = ServiceHealthStatus(
            _required_text(
                payload.get("status"),
                "health.status",
            )
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            "health.status is invalid"
        ) from exc

    return ServiceHealth(
        status=status,
        score=_required_int(
            payload.get("score", 100),
            "health.score",
        ),
        warnings=warnings,
        errors=errors,
        details=details,
        evaluated_at=_required_text(
            payload.get("evaluated_at"),
            "health.evaluated_at",
        ),
    )


def _parse_image_reference(
    payload: Mapping[str, Any],
    field: str,
) -> ImageReference:
    return ImageReference(
        repository=_required_text(
            payload.get("repository"),
            f"{field}.repository",
        ),
        tag=_optional_text(
            payload.get("tag"),
            f"{field}.tag",
        ),
        digest=_optional_text(
            payload.get("digest"),
            f"{field}.digest",
        ),
        raw_reference=_optional_text(
            payload.get("raw_reference"),
            f"{field}.raw_reference",
        ),
    )


def _parse_update(
    payload: Mapping[str, Any],
) -> ServiceUpdate:
    try:
        status = UpdateStatus(
            _required_text(
                payload.get("status"),
                "update.status",
            )
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            "update.status is invalid"
        ) from exc

    current_image = _parse_image_reference(
        _mapping(
            payload.get("current_image"),
            "update.current_image",
        ),
        "update.current_image",
    )

    available_value = payload.get(
        "available_image"
    )

    available_image = (
        None
        if available_value is None
        else _parse_image_reference(
            _mapping(
                available_value,
                "update.available_image",
            ),
            "update.available_image",
        )
    )

    details = payload.get("details", {})

    if not isinstance(details, dict):
        raise ServiceLifecycleError(
            "update.details must be an object"
        )

    return ServiceUpdate(
        service_identifier=_required_text(
            payload.get("service_identifier"),
            "update.service_identifier",
        ),
        service_name=_required_text(
            payload.get("service_name"),
            "update.service_name",
        ),
        current_image=current_image,
        status=status,
        available_image=available_image,
        reason=_optional_text(
            payload.get("reason"),
            "update.reason",
        ),
        details=details,
        evaluated_at=_required_text(
            payload.get("evaluated_at"),
            "update.evaluated_at",
        ),
    )


def _parse_maintenance_record(
    payload: Mapping[str, Any],
) -> MaintenanceRecord:
    try:
        action = MaintenanceAction(
            _required_text(
                payload.get("action"),
                "history.records[].action",
            )
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            "maintenance action is invalid"
        ) from exc

    try:
        result = MaintenanceResult(
            _required_text(
                payload.get("result"),
                "history.records[].result",
            )
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            "maintenance result is invalid"
        ) from exc

    details = payload.get("details", {})

    if not isinstance(details, dict):
        raise ServiceLifecycleError(
            "maintenance details must be an object"
        )

    return MaintenanceRecord(
        service_identifier=_required_text(
            payload.get("service_identifier"),
            "history.records[].service_identifier",
        ),
        service_name=_required_text(
            payload.get("service_name"),
            "history.records[].service_name",
        ),
        action=action,
        result=result,
        started_at=_required_text(
            payload.get("started_at"),
            "history.records[].started_at",
        ),
        completed_at=_optional_text(
            payload.get("completed_at"),
            "history.records[].completed_at",
        ),
        provider=_required_text(
            payload.get("provider", "unknown"),
            "history.records[].provider",
        ),
        summary=_optional_text(
            payload.get("summary"),
            "history.records[].summary",
        ),
        details=details,
    )


def _parse_maintenance_report(
    payload: Mapping[str, Any],
) -> MaintenanceReport:
    records_value = payload.get(
        "records",
        [],
    )

    if not isinstance(records_value, list):
        raise ServiceLifecycleError(
            "history.records must be a list"
        )

    return MaintenanceReport(
        records=tuple(
            _parse_maintenance_record(
                _mapping(
                    record,
                    "history.records[]",
                )
            )
            for record in records_value
        ),
        provider=_required_text(
            payload.get("provider", "unknown"),
            "history.provider",
        ),
        generated_at=_required_text(
            payload.get("generated_at"),
            "history.generated_at",
        ),
    )


def _mapping(
    value: object,
    field: str,
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ServiceLifecycleError(
            f"{field} must be an object"
        )

    return value


def _required_text(
    value: object,
    field: str,
) -> str:
    if not isinstance(value, str):
        raise ServiceLifecycleError(
            f"{field} must be non-empty text"
        )

    normalized = value.strip()

    if not normalized:
        raise ServiceLifecycleError(
            f"{field} must be non-empty text"
        )

    return normalized


def _optional_text(
    value: object,
    field: str,
) -> str | None:
    if value is None:
        return None

    return _required_text(
        value,
        field,
    )


def _required_bool(
    value: object,
    field: str,
) -> bool:
    if not isinstance(value, bool):
        raise ServiceLifecycleError(
            f"{field} must be a boolean"
        )

    return value


def _required_int(
    value: object,
    field: str,
) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
    ):
        raise ServiceLifecycleError(
            f"{field} must be an integer"
        )

    return value


def _optional_int(
    value: object,
    field: str,
) -> int | None:
    if value is None:
        return None

    return _required_int(
        value,
        field,
    )


def _text_list(
    value: object,
    field: str,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ServiceLifecycleError(
            f"{field} must be a list"
        )

    return tuple(
        _required_text(
            item,
            f"{field}[]",
        )
        for item in value
    )
