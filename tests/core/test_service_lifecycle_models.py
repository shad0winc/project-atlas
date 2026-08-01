"""Contract tests for Atlas Service Lifecycle models."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    ManagedService,
    ServiceLifecycleError,
)


def make_service(**overrides: object) -> ManagedService:
    values: dict[str, object] = {
        "identifier": "sonarr",
        "name": "Sonarr",
        "provider": "docker-compose",
    }
    values.update(overrides)

    return ManagedService(**values)


def test_managed_service_normalizes_identity_and_text() -> None:
    service = ManagedService(
        identifier="  Sonarr-Anime  ",
        name="  Sonarr Anime  ",
        provider="  Docker-Compose  ",
        compose_project="  project-atlas  ",
        container_name="  sonarr-anime  ",
    )

    assert service.identifier == "sonarr-anime"
    assert service.name == "Sonarr Anime"
    assert service.provider == "docker-compose"
    assert service.compose_project == "project-atlas"
    assert service.container_name == "sonarr-anime"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            100,
            "100",
        ),
        (
            "Prowlarr",
            "prowlarr",
        ),
        (
            "sonarr_anime",
            "sonarr_anime",
        ),
        (
            "radarr.anime",
            "radarr.anime",
        ),
    ],
)
def test_managed_service_normalizes_supported_identifiers(
    value: object,
    expected: str,
) -> None:
    service = ManagedService(
        identifier=value,  # type: ignore[arg-type]
        name="Service",
        provider="docker-compose",
    )

    assert service.identifier == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        object(),
        "-sonarr",
        "sonarr-",
        ".sonarr",
        "sonarr.",
        "son arr",
        "sonarr/api",
        "sonarr:latest",
        "sonarr@atlas",
    ],
)
def test_managed_service_rejects_invalid_identifiers(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="identifier",
    ):
        ManagedService(
            identifier=value,  # type: ignore[arg-type]
            name="Sonarr",
            provider="docker-compose",
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        object(),
        "-docker",
        "docker-",
        "docker compose",
        "docker/compose",
    ],
)
def test_managed_service_rejects_invalid_provider(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="provider",
    ):
        ManagedService(
            identifier="sonarr",
            name="Sonarr",
            provider=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        42,
        object(),
    ],
)
def test_managed_service_requires_display_name(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="name is required",
    ):
        ManagedService(
            identifier="sonarr",
            name=value,  # type: ignore[arg-type]
            provider="docker-compose",
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        " project-atlas ",
    ],
)
def test_managed_service_normalizes_optional_compose_project(
    value: object,
) -> None:
    service = make_service(
        compose_project=value,
    )

    expected = (
        None
        if value is None
        else "project-atlas"
    )

    assert service.compose_project == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        True,
        42,
        object(),
    ],
)
def test_managed_service_rejects_invalid_compose_project(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "compose_project must be non-empty text or null"
        ),
    ):
        make_service(
            compose_project=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        " sonarr ",
    ],
)
def test_managed_service_normalizes_optional_container_name(
    value: object,
) -> None:
    service = make_service(
        container_name=value,
    )

    expected = (
        None
        if value is None
        else "sonarr"
    )

    assert service.container_name == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        True,
        42,
        object(),
    ],
)
def test_managed_service_rejects_invalid_container_name(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "container_name must be non-empty text or null"
        ),
    ):
        make_service(
            container_name=value,
        )


def test_managed_service_normalizes_dependencies_deterministically() -> None:
    service = make_service(
        dependencies=[
            "Prowlarr",
            " gluetun ",
            "prowlarr",
            "Radarr",
        ],
    )

    assert service.dependencies == (
        "gluetun",
        "prowlarr",
        "radarr",
    )


@pytest.mark.parametrize(
    "value",
    [
        "prowlarr",
        b"prowlarr",
        42,
        True,
        object(),
    ],
)
def test_managed_service_requires_dependency_collection(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="dependencies must be a collection",
    ):
        make_service(
            dependencies=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        object(),
        "-prowlarr",
        "prowlarr/",
    ],
)
def test_managed_service_rejects_invalid_dependency(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="dependencies value",
    ):
        make_service(
            dependencies=[
                value,
            ],
        )


def test_managed_service_rejects_self_dependency() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "dependencies must not contain "
            "the service identifier"
        ),
    ):
        make_service(
            dependencies=[
                "sonarr",
            ],
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            None,
            None,
        ),
        (
            "2026-08-01T09:00:00-04:00",
            "2026-08-01T13:00:00Z",
        ),
        (
            "2026-08-01T13:00:00Z",
            "2026-08-01T13:00:00Z",
        ),
    ],
)
def test_managed_service_normalizes_timestamps(
    value: object,
    expected: str | None,
) -> None:
    service = make_service(
        created_at=value,
        updated_at=value,
    )

    assert service.created_at == expected
    assert service.updated_at == expected


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        True,
        42,
        object(),
        "2026-08-01",
        "not-a-timestamp",
    ],
)
def test_managed_service_rejects_invalid_created_at(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="created_at",
    ):
        make_service(
            created_at=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        True,
        42,
        object(),
        "2026-08-01",
        "not-a-timestamp",
    ],
)
def test_managed_service_rejects_invalid_updated_at(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="updated_at",
    ):
        make_service(
            updated_at=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        False,
    ],
)
def test_managed_service_requires_boolean_enabled(
    value: object,
) -> None:
    if isinstance(value, bool):
        service = make_service(
            enabled=value,
        )
        assert service.enabled is value
        return

    with pytest.raises(
        ServiceLifecycleError,
        match="enabled must be a boolean",
    ):
        make_service(
            enabled=value,
        )


def test_managed_service_is_immutable() -> None:
    service = make_service()

    with pytest.raises(FrozenInstanceError):
        service.name = "Changed"  # type: ignore[misc]


def test_managed_service_serializes_normalized_contract() -> None:
    service = ManagedService(
        identifier=" Sonarr-Anime ",
        name=" Sonarr Anime ",
        provider=" Docker-Compose ",
        enabled=False,
        compose_project=" project-atlas ",
        container_name=" sonarr-anime ",
        dependencies=[
            "Prowlarr",
            "gluetun",
            "prowlarr",
        ],
        created_at="2026-08-01T09:00:00-04:00",
        updated_at="2026-08-01T10:00:00-04:00",
    )

    assert service.to_dict() == {
        "identifier": "sonarr-anime",
        "name": "Sonarr Anime",
        "provider": "docker-compose",
        "enabled": False,
        "compose_project": "project-atlas",
        "container_name": "sonarr-anime",
        "dependencies": [
            "gluetun",
            "prowlarr",
        ],
        "created_at": "2026-08-01T13:00:00Z",
        "updated_at": "2026-08-01T14:00:00Z",
    }


def test_service_lifecycle_package_exports_public_contracts() -> None:
    from atlas import service_lifecycle

    assert service_lifecycle.ManagedService is ManagedService
    assert (
        service_lifecycle.ServiceLifecycleError
        is ServiceLifecycleError
    )
