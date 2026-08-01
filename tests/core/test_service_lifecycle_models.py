"""Contract tests for Atlas Service Lifecycle models."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    ManagedService,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRuntime,
)


def make_service(**overrides: object) -> ManagedService:
    values: dict[str, object] = {
        "identifier": "sonarr",
        "name": "Sonarr",
        "provider": "docker-compose",
    }
    values.update(overrides)

    return ManagedService(**values)


def make_image(**overrides: object) -> ServiceImage:
    values: dict[str, object] = {
        "reference": "lscr.io/linuxserver/sonarr:latest",
    }
    values.update(overrides)

    return ServiceImage(**values)


def make_runtime(**overrides: object) -> ServiceRuntime:
    values: dict[str, object] = {
        "state": "running",
        "health": "healthy",
        "image": make_image(),
    }
    values.update(overrides)

    return ServiceRuntime(**values)


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

def test_service_image_normalizes_contract() -> None:
    digest = "sha256:" + ("a" * 64)
    image_id = "sha256:" + ("b" * 64)

    image = ServiceImage(
        reference="  lscr.io/linuxserver/sonarr:latest  ",
        repository="  lscr.io/linuxserver/sonarr  ",
        tag="  latest  ",
        digest=digest.upper(),
        image_id=image_id.upper(),
        created_at="2026-08-01T09:00:00-04:00",
    )

    assert image.reference == "lscr.io/linuxserver/sonarr:latest"
    assert image.repository == "lscr.io/linuxserver/sonarr"
    assert image.tag == "latest"
    assert image.digest == digest
    assert image.image_id == image_id
    assert image.created_at == "2026-08-01T13:00:00Z"


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
def test_service_image_requires_reference(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="reference is required",
    ):
        ServiceImage(
            reference=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "repository",
        "tag",
    ],
)
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
def test_service_image_rejects_invalid_optional_text(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=(
            rf"{field_name} must be non-empty text or null"
        ),
    ):
        make_image(
            **{
                field_name: value,
            },
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "digest",
        "image_id",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        True,
        42,
        object(),
        "md5:" + ("a" * 32),
        "sha256:",
        "sha256:" + ("a" * 63),
        "sha256:" + ("a" * 65),
        "sha256:" + ("g" * 64),
    ],
)
def test_service_image_rejects_invalid_digest(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=field_name,
    ):
        make_image(
            **{
                field_name: value,
            },
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
def test_service_image_normalizes_created_at(
    value: object,
    expected: str | None,
) -> None:
    image = make_image(
        created_at=value,
    )

    assert image.created_at == expected


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
def test_service_image_rejects_invalid_created_at(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="created_at",
    ):
        make_image(
            created_at=value,
        )


def test_service_image_is_immutable() -> None:
    image = make_image()

    with pytest.raises(FrozenInstanceError):
        image.tag = "changed"  # type: ignore[misc]


def test_service_image_serializes_normalized_contract() -> None:
    digest = "sha256:" + ("a" * 64)
    image_id = "sha256:" + ("b" * 64)

    image = ServiceImage(
        reference=" sonarr:latest ",
        repository=" sonarr ",
        tag=" latest ",
        digest=digest,
        image_id=image_id,
        created_at="2026-08-01T09:00:00-04:00",
    )

    assert image.to_dict() == {
        "reference": "sonarr:latest",
        "repository": "sonarr",
        "tag": "latest",
        "digest": digest,
        "image_id": image_id,
        "created_at": "2026-08-01T13:00:00Z",
    }


def test_service_runtime_normalizes_contract() -> None:
    runtime = ServiceRuntime(
        state=" Running ",
        health=" Healthy ",
        image=make_image(),
        restart_count=3,
        started_at="2026-08-01T09:00:00-04:00",
        finished_at="2026-08-01T10:00:00-04:00",
        exit_code=0,
        status_message=" Up one hour ",
    )

    assert runtime.state == "running"
    assert runtime.health == "healthy"
    assert runtime.restart_count == 3
    assert runtime.started_at == "2026-08-01T13:00:00Z"
    assert runtime.finished_at == "2026-08-01T14:00:00Z"
    assert runtime.exit_code == 0
    assert runtime.status_message == "Up one hour"
    assert runtime.running is True
    assert runtime.healthy is True


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (
            "running",
            True,
        ),
        (
            "exited",
            False,
        ),
        (
            "restarting",
            False,
        ),
        (
            "created",
            False,
        ),
    ],
)
def test_service_runtime_running_property(
    state: str,
    expected: bool,
) -> None:
    runtime = make_runtime(
        state=state,
    )

    assert runtime.running is expected


@pytest.mark.parametrize(
    ("health", "expected"),
    [
        (
            "healthy",
            True,
        ),
        (
            "unhealthy",
            False,
        ),
        (
            "starting",
            False,
        ),
        (
            "unknown",
            False,
        ),
    ],
)
def test_service_runtime_healthy_property(
    health: str,
    expected: bool,
) -> None:
    runtime = make_runtime(
        health=health,
    )

    assert runtime.healthy is expected


@pytest.mark.parametrize(
    "field_name",
    [
        "state",
        "health",
    ],
)
@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        None,
        True,
        object(),
        "-running",
        "running-",
        "running state",
        "running/state",
    ],
)
def test_service_runtime_rejects_invalid_state_identity(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=field_name,
    ):
        make_runtime(
            **{
                field_name: value,
            },
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        True,
        0,
        "image",
        object(),
    ],
)
def test_service_runtime_requires_service_image(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="image must be a ServiceImage",
    ):
        make_runtime(
            image=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        -1,
        True,
        None,
        1.5,
        "1",
        object(),
    ],
)
def test_service_runtime_rejects_invalid_restart_count(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "restart_count must be a non-negative integer"
        ),
    ):
        make_runtime(
            restart_count=value,
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "started_at",
        "finished_at",
    ],
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
def test_service_runtime_rejects_invalid_timestamp(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=field_name,
    ):
        make_runtime(
            **{
                field_name: value,
            },
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        1.5,
        "0",
        object(),
    ],
)
def test_service_runtime_rejects_invalid_exit_code(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="exit_code must be an integer or null",
    ):
        make_runtime(
            exit_code=value,
        )


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
def test_service_runtime_rejects_invalid_status_message(
    value: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match=(
            "status_message must be non-empty text or null"
        ),
    ):
        make_runtime(
            status_message=value,
        )


def test_service_runtime_is_immutable() -> None:
    runtime = make_runtime()

    with pytest.raises(FrozenInstanceError):
        runtime.state = "stopped"  # type: ignore[misc]


def test_service_runtime_serializes_child_contract() -> None:
    runtime = ServiceRuntime(
        state="running",
        health="healthy",
        image=make_image(
            repository="sonarr",
            tag="latest",
        ),
        restart_count=2,
        started_at="2026-08-01T09:00:00-04:00",
        finished_at=None,
        exit_code=None,
        status_message="Up one hour",
    )

    assert runtime.to_dict() == {
        "state": "running",
        "health": "healthy",
        "running": True,
        "healthy": True,
        "image": {
            "reference": "lscr.io/linuxserver/sonarr:latest",
            "repository": "sonarr",
            "tag": "latest",
            "digest": None,
            "image_id": None,
            "created_at": None,
        },
        "restart_count": 2,
        "started_at": "2026-08-01T13:00:00Z",
        "finished_at": None,
        "exit_code": None,
        "status_message": "Up one hour",
    }


def test_service_lifecycle_package_exports_runtime_contracts() -> None:
    from atlas import service_lifecycle

    assert service_lifecycle.ServiceImage is ServiceImage
    assert service_lifecycle.ServiceRuntime is ServiceRuntime
