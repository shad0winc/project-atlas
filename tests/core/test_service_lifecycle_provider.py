"""Contract tests for the Service Lifecycle provider interface."""

from abc import ABC
import inspect

import pytest

from atlas.service_lifecycle import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleProvider,
    ServiceRuntime,
    ImageReference,
    ServiceUpdate,
    UpdateStatus,
)


class StubProvider(ServiceLifecycleProvider):
    """Minimal provider used to verify the abstract contract."""

    def __init__(self) -> None:
        self.service = ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider="stub",
        )
        self.image = ServiceImage(
            reference="sonarr:latest",
        )
        self.runtime = ServiceRuntime(
            state="running",
            health="healthy",
            image=self.image,
        )
        self.health = ServiceHealth(
            status=ServiceHealthStatus.HEALTHY,
        )
        self.update = ServiceUpdate(
            service_identifier="sonarr",
            service_name="Sonarr",
            current_image=ImageReference.parse("sonarr:latest"),
            status=UpdateStatus.MUTABLE_TAG,
        )

    def list_services(self):
        return (
            self.service,
        )

    def inspect_service(
        self,
        identifier: str,
    ) -> ManagedService:
        if identifier != self.service.identifier:
            raise LookupError(identifier)

        return self.service

    def inspect_runtime(
        self,
        identifier: str,
    ) -> ServiceRuntime:
        if identifier != self.service.identifier:
            raise LookupError(identifier)

        return self.runtime

    def inspect_health(
        self,
        identifier: str,
    ) -> ServiceHealth:
        if identifier != self.service.identifier:
            raise LookupError(identifier)

        return self.health

    def inspect_update(
        self,
        identifier: str,
    ) -> ServiceUpdate:
        if identifier != self.service.identifier:
            raise LookupError(identifier)

        return self.update


def test_provider_contract_is_abstract_base_class() -> None:
    assert issubclass(ServiceLifecycleProvider, ABC)
    assert inspect.isabstract(ServiceLifecycleProvider)


@pytest.mark.parametrize(
    "method_name",
    [
        "list_services",
        "inspect_service",
        "inspect_runtime",
        "inspect_health",
        "inspect_update",
    ],
)
def test_provider_contract_declares_abstract_methods(
    method_name: str,
) -> None:
    method = getattr(
        ServiceLifecycleProvider,
        method_name,
    )

    assert getattr(
        method,
        "__isabstractmethod__",
        False,
    )


def test_provider_contract_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        ServiceLifecycleProvider()


def test_complete_provider_can_be_instantiated() -> None:
    provider = StubProvider()

    assert isinstance(
        provider,
        ServiceLifecycleProvider,
    )


def test_provider_lists_normalized_services() -> None:
    provider = StubProvider()

    assert provider.list_services() == (
        provider.service,
    )


def test_provider_inspects_normalized_service() -> None:
    provider = StubProvider()

    assert (
        provider.inspect_service("sonarr")
        is provider.service
    )


def test_provider_inspects_normalized_runtime() -> None:
    provider = StubProvider()

    assert (
        provider.inspect_runtime("sonarr")
        is provider.runtime
    )


def test_provider_inspects_normalized_health() -> None:
    provider = StubProvider()

    assert (
        provider.inspect_health("sonarr")
        is provider.health
    )


def test_provider_inspects_normalized_update() -> None:
    provider = StubProvider()

    assert provider.inspect_update("sonarr") is provider.update


@pytest.mark.parametrize(
    "method_name",
    [
        "inspect_service",
        "inspect_runtime",
        "inspect_health",
        "inspect_update",
    ],
)
def test_stub_provider_rejects_unknown_service(
    method_name: str,
) -> None:
    provider = StubProvider()
    method = getattr(
        provider,
        method_name,
    )

    with pytest.raises(
        LookupError,
        match="unknown",
    ):
        method("unknown")


def test_service_lifecycle_package_exports_provider_contract() -> None:
    from atlas import service_lifecycle

    assert (
        service_lifecycle.ServiceLifecycleProvider
        is ServiceLifecycleProvider
    )
