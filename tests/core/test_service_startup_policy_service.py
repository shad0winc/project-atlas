"""Tests for startup-policy lifecycle orchestration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from atlas.service_lifecycle import (
    DockerComposeProvider,
    ManagedService,
    ServiceLifecycleError,
    ServiceLifecycleService,
    ServiceStartupContract,
    ServiceStartupPolicyService,
)


def lifecycle_with_provider(
    tmp_path: Path,
) -> tuple[
    ServiceLifecycleService,
    DockerComposeProvider,
]:
    compose_file = tmp_path / "compose.yml"
    compose_file.write_text(
        "services:\n"
        "  sonarr:\n"
        "    image: sonarr:latest\n",
        encoding="utf-8",
    )

    provider = DockerComposeProvider(
        compose_file=compose_file,
    )

    return (
        ServiceLifecycleService(
            provider,
        ),
        provider,
    )


def startup_contract() -> ServiceStartupContract:
    return ServiceStartupContract(
        service=ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider="docker-compose",
            container_name="sonarr",
        ),
        restart_policy="unless-stopped",
    )


def test_startup_policy_service_is_immutable(
    tmp_path: Path,
) -> None:
    lifecycle, _ = lifecycle_with_provider(
        tmp_path,
    )

    service = ServiceStartupPolicyService(
        lifecycle,
    )

    with pytest.raises(FrozenInstanceError):
        service.lifecycle = lifecycle  # type: ignore[misc]


def test_startup_policy_service_validates_lifecycle() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="lifecycle must be ServiceLifecycleService",
    ):
        ServiceStartupPolicyService(
            object(),  # type: ignore[arg-type]
        )


def test_startup_policy_service_evaluates_provider_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle, _ = lifecycle_with_provider(
        tmp_path,
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_startup_contracts",
        lambda self: (
            startup_contract(),
        ),
    )

    report = ServiceStartupPolicyService(
        lifecycle,
    ).inspect()

    assert report.provider == "docker-compose"
    assert report.findings == ()
    assert report.passed is True


def test_startup_policy_service_preserves_domain_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle, _ = lifecycle_with_provider(
        tmp_path,
    )

    def fail(
        self: DockerComposeProvider,
    ) -> tuple[ServiceStartupContract, ...]:
        raise ServiceLifecycleError(
            "known startup failure",
        )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_startup_contracts",
        fail,
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="known startup failure",
    ):
        ServiceStartupPolicyService(
            lifecycle,
        ).inspect()


def test_startup_policy_service_translates_provider_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle, _ = lifecycle_with_provider(
        tmp_path,
    )

    def fail(
        self: DockerComposeProvider,
    ) -> tuple[ServiceStartupContract, ...]:
        raise RuntimeError(
            "provider exploded",
        )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_startup_contracts",
        fail,
    )

    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "service provider failed to inspect "
            "startup contracts"
        ),
    ):
        ServiceStartupPolicyService(
            lifecycle,
        ).inspect()


@pytest.mark.parametrize(
    "value",
    (
        None,
        "contracts",
        b"contracts",
        42,
        object(),
    ),
)
def test_startup_policy_service_requires_collection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: object,
) -> None:
    lifecycle, _ = lifecycle_with_provider(
        tmp_path,
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_startup_contracts",
        lambda self: value,
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="startup contracts must be a collection",
    ):
        ServiceStartupPolicyService(
            lifecycle,
        ).inspect()


def test_startup_policy_service_validates_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lifecycle, _ = lifecycle_with_provider(
        tmp_path,
    )

    monkeypatch.setattr(
        DockerComposeProvider,
        "inspect_startup_contracts",
        lambda self: (
            object(),
        ),
    )

    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "startup contracts must contain "
            "ServiceStartupContract objects"
        ),
    ):
        ServiceStartupPolicyService(
            lifecycle,
        ).inspect()
