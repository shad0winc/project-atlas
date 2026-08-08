"""Read-only orchestration for Service Lifecycle maintenance history."""

from __future__ import annotations

from dataclasses import dataclass

from ..maintenance_models import (
    MaintenanceRecord,
    MaintenanceReport,
)
from ..models import (
    ManagedService,
    ServiceLifecycleError,
)
from .lifecycle import ServiceLifecycleService


@dataclass(frozen=True)
class ServiceMaintenanceHistoryService:
    """Validate provider maintenance-history reports."""

    lifecycle: ServiceLifecycleService

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle, ServiceLifecycleService):
            raise ServiceLifecycleError(
                "lifecycle must be ServiceLifecycleService",
            )

    def inspect_history(self) -> MaintenanceReport:
        """Return validated history for all managed services."""

        try:
            report = self.lifecycle.provider.inspect_history()
        except ServiceLifecycleError:
            raise
        except Exception as exc:
            raise ServiceLifecycleError(
                "service provider failed to inspect maintenance history",
            ) from exc

        return self._validate_report(report)

    def inspect_service_history(
        self,
        identifier: str,
    ) -> MaintenanceReport:
        """Return validated maintenance history for one service."""

        service = self.lifecycle.inspect_service(identifier)

        try:
            report = self.lifecycle.provider.inspect_service_history(
                service.identifier,
            )
        except ServiceLifecycleError:
            raise
        except Exception as exc:
            raise ServiceLifecycleError(
                "service provider failed to inspect maintenance history: "
                f"{service.identifier}",
            ) from exc

        validated = self._validate_report(report)
        self._validate_service_records(
            service,
            validated.records,
        )
        return validated

    @staticmethod
    def _validate_report(
        report: object,
    ) -> MaintenanceReport:
        if not isinstance(report, MaintenanceReport):
            raise ServiceLifecycleError(
                "provider maintenance history must return "
                "MaintenanceReport",
            )
        return report

    @staticmethod
    def _validate_service_records(
        service: ManagedService,
        records: tuple[MaintenanceRecord, ...],
    ) -> None:
        for record in records:
            if record.service_identifier != service.identifier:
                raise ServiceLifecycleError(
                    "provider returned mismatched maintenance "
                    "service identifier: "
                    f"expected {service.identifier}, "
                    f"received {record.service_identifier}",
                )

            if record.service_name != service.name:
                raise ServiceLifecycleError(
                    "provider returned mismatched maintenance "
                    "service name: "
                    f"expected {service.name}, "
                    f"received {record.service_name}",
                )
