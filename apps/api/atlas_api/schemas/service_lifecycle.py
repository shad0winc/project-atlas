"""Read-only Service Lifecycle response schemas for the Atlas API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ManagedServiceListResponse(BaseModel):
    """Normalized managed-service collection."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    count: int
    services: tuple[dict[str, Any], ...]

    @classmethod
    def from_domain(
        cls,
        services: tuple[object, ...],
    ) -> "ManagedServiceListResponse":
        """Adapt normalized Service Lifecycle domain objects."""

        serialized = tuple(
            _serialize_domain(item)
            for item in services
        )

        return cls(
            count=len(serialized),
            services=serialized,
        )


class ManagedServiceDetailResponse(BaseModel):
    """Normalized detail for one Atlas-managed service."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    service: dict[str, Any]

    @classmethod
    def from_domain(
        cls,
        service: object,
    ) -> "ManagedServiceDetailResponse":
        """Adapt one normalized ManagedService."""

        return cls(
            service=_serialize_domain(service),
        )


class ServiceLifecycleHealthResponse(BaseModel):
    """Aggregate read-only Service Lifecycle health."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    health: dict[str, Any]

    @classmethod
    def from_domain(
        cls,
        health: object,
    ) -> "ServiceLifecycleHealthResponse":
        """Adapt one InfrastructureHealthReport."""

        return cls(
            health=_serialize_domain(health),
        )


class ServiceLifecycleSummaryResponse(BaseModel):
    """Aggregate read-only infrastructure summary."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    summary: dict[str, Any]

    @classmethod
    def from_domain(
        cls,
        summary: object,
    ) -> "ServiceLifecycleSummaryResponse":
        """Adapt one InfrastructureSummary."""

        return cls(
            summary=_serialize_domain(summary),
        )


def _serialize_domain(
    value: object,
) -> dict[str, Any]:
    """Require and copy canonical domain serialization."""

    serializer = getattr(value, "to_dict", None)

    if not callable(serializer):
        raise TypeError(
            "Service Lifecycle API values must expose to_dict()"
        )

    payload = serializer()

    if not isinstance(payload, dict):
        raise TypeError(
            "Service Lifecycle to_dict() must return a dictionary"
        )

    return dict(payload)


__all__ = [
    "ManagedServiceDetailResponse",
    "ManagedServiceListResponse",
    "ServiceLifecycleHealthResponse",
    "ServiceLifecycleSummaryResponse",
]
