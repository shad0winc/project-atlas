"""Tests for normalized Service Lifecycle update-discovery contracts."""

from __future__ import annotations

import pytest

from atlas.service_lifecycle import (
    ImageReference,
    ServiceLifecycleError,
    ServiceUpdate,
    UpdateReport,
    UpdateStatus,
)


TIMESTAMP = "2026-08-02T01:30:00Z"
DIGEST = "sha256:" + ("a" * 64)
NEW_DIGEST = "sha256:" + ("b" * 64)


def make_image(**overrides: object) -> ImageReference:
    values: dict[str, object] = {
        "repository": "lscr.io/linuxserver/sonarr",
        "tag": "4.0.15",
        "digest": DIGEST,
    }
    values.update(overrides)
    return ImageReference(**values)  # type: ignore[arg-type]


def make_update(**overrides: object) -> ServiceUpdate:
    values: dict[str, object] = {
        "service_identifier": "sonarr",
        "service_name": "Sonarr",
        "current_image": make_image(),
        "status": UpdateStatus.CURRENT,
        "reason": "The current and available digests match.",
        "details": {"source": "registry"},
        "evaluated_at": TIMESTAMP,
    }
    values.update(overrides)
    return ServiceUpdate(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("raw", "repository", "tag", "digest"),
    [
        (
            "lscr.io/linuxserver/sonarr:4.0.15",
            "lscr.io/linuxserver/sonarr",
            "4.0.15",
            None,
        ),
        (
            "jellyfin/jellyfin",
            "jellyfin/jellyfin",
            "latest",
            None,
        ),
        (
            f"registry.example:5000/team/app:stable@{DIGEST}",
            "registry.example:5000/team/app",
            "stable",
            DIGEST,
        ),
    ],
)
def test_image_reference_parse_normalizes_docker_references(
    raw: str,
    repository: str,
    tag: str,
    digest: str | None,
) -> None:
    image = ImageReference.parse(raw)

    assert image.repository == repository
    assert image.tag == tag
    assert image.digest == digest
    assert image.raw_reference == raw


def test_image_reference_normalizes_and_serializes() -> None:
    image = ImageReference(
        repository="  LSCR.IO/LinuxServer/Sonarr  ",
        tag=" stable ",
        digest=f" SHA256:{'A' * 64} ",
    )

    assert image.repository == "lscr.io/linuxserver/sonarr"
    assert image.tag == "stable"
    assert image.digest == DIGEST
    assert image.raw_reference == (
        f"lscr.io/linuxserver/sonarr:stable@{DIGEST}"
    )
    assert image.canonical_reference == image.raw_reference
    assert image.is_mutable is False
    assert image.to_dict()["is_mutable"] is False


def test_image_reference_identifies_latest_as_mutable() -> None:
    image = ImageReference.parse("jellyfin/jellyfin")

    assert image.tag == "latest"
    assert image.is_mutable is True


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("repository", "bad repository", "invalid repository"),
        ("repository", "/bad", "invalid repository"),
        ("tag", ".bad", "invalid tag"),
        ("tag", "bad tag", "invalid tag"),
        ("digest", "sha256:short", "invalid digest"),
    ],
)
def test_image_reference_rejects_invalid_contracts(
    field_name: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ServiceLifecycleError, match=message):
        make_image(**{field_name: value})


@pytest.mark.parametrize(
    "value",
    ["", "   ", "@sha256:" + ("a" * 64), "repo:"],
)
def test_image_reference_parse_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ServiceLifecycleError):
        ImageReference.parse(value)


def test_service_update_normalizes_and_serializes() -> None:
    available = make_image(digest=NEW_DIGEST)
    update = make_update(
        service_identifier=" SONARR ",
        service_name="  Sonarr  ",
        status=" UPDATE-AVAILABLE ",
        available_image=available,
        reason="  A different registry digest is available.  ",
        evaluated_at="2026-08-01T21:30:00-04:00",
    )

    assert update.service_identifier == "sonarr"
    assert update.service_name == "Sonarr"
    assert update.status is UpdateStatus.UPDATE_AVAILABLE
    assert update.available_image is available
    assert update.reason == "A different registry digest is available."
    assert update.evaluated_at == TIMESTAMP
    assert update.requires_attention is True
    assert update.to_dict()["available_image"]["digest"] == NEW_DIGEST


@pytest.mark.parametrize(
    ("status", "requires_attention"),
    [
        (UpdateStatus.CURRENT, False),
        (UpdateStatus.UPDATE_AVAILABLE, True),
        (UpdateStatus.MUTABLE_TAG, True),
        (UpdateStatus.UNKNOWN, False),
        (UpdateStatus.UNSUPPORTED, False),
    ],
)
def test_service_update_attention_contract(
    status: UpdateStatus,
    requires_attention: bool,
) -> None:
    available = (
        make_image(digest=NEW_DIGEST)
        if status is UpdateStatus.UPDATE_AVAILABLE
        else None
    )
    update = make_update(status=status, available_image=available)

    assert update.requires_attention is requires_attention


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "service_identifier",
            "bad/value",
            "invalid service_identifier",
        ),
        ("service_name", "   ", "service_name must be non-empty text"),
        ("status", "pending", "invalid status"),
        (
            "evaluated_at",
            "2026-08-02T01:30:00",
            "evaluated_at must include a timezone",
        ),
    ],
)
def test_service_update_rejects_invalid_scalar_contracts(
    field_name: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ServiceLifecycleError, match=message):
        make_update(**{field_name: value})


def test_service_update_validates_child_contracts() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="current_image must be an ImageReference",
    ):
        make_update(current_image="image")

    with pytest.raises(
        ServiceLifecycleError,
        match="available_image must be an ImageReference",
    ):
        make_update(available_image="image")


def test_service_update_requires_available_image_for_update() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="available_image is required",
    ):
        make_update(status=UpdateStatus.UPDATE_AVAILABLE)


def test_service_update_requires_details_mapping() -> None:
    with pytest.raises(ServiceLifecycleError, match="details must be an object"):
        make_update(details=[("source", "registry")])


@pytest.mark.parametrize(
    ("statuses", "expected"),
    [
        ((), "current"),
        ((UpdateStatus.CURRENT,), "current"),
        ((UpdateStatus.UNKNOWN,), "incomplete"),
        ((UpdateStatus.UNSUPPORTED,), "incomplete"),
        ((UpdateStatus.MUTABLE_TAG,), "attention"),
        ((UpdateStatus.UPDATE_AVAILABLE,), "updates-available"),
        (
            (UpdateStatus.MUTABLE_TAG, UpdateStatus.UPDATE_AVAILABLE),
            "updates-available",
        ),
    ],
)
def test_update_report_status_uses_highest_priority(
    statuses: tuple[UpdateStatus, ...],
    expected: str,
) -> None:
    updates = tuple(
        make_update(
            service_identifier=f"service-{index}",
            status=status,
            available_image=(
                make_image(digest=NEW_DIGEST)
                if status is UpdateStatus.UPDATE_AVAILABLE
                else None
            ),
        )
        for index, status in enumerate(statuses, start=1)
    )

    assert UpdateReport(
        updates=updates,
        provider="docker-compose",
        evaluated_at=TIMESTAMP,
    ).status == expected


def test_update_report_orders_counts_and_serializes() -> None:
    current = make_update(
        service_identifier="current",
        status=UpdateStatus.CURRENT,
    )
    mutable = make_update(
        service_identifier="mutable",
        status=UpdateStatus.MUTABLE_TAG,
        current_image=ImageReference.parse("example/app:latest"),
    )
    available = make_update(
        service_identifier="available",
        status=UpdateStatus.UPDATE_AVAILABLE,
        available_image=make_image(digest=NEW_DIGEST),
    )
    unknown = make_update(
        service_identifier="unknown",
        status=UpdateStatus.UNKNOWN,
    )

    report = UpdateReport(
        updates=[current, unknown, mutable, available],  # type: ignore[arg-type]
        provider=" DOCKER-COMPOSE ",
        evaluated_at="2026-08-01T21:30:00-04:00",
    )

    assert report.updates == (available, mutable, unknown, current)
    assert report.provider == "docker-compose"
    assert report.evaluated_at == TIMESTAMP
    assert report.status == "updates-available"
    assert report.requires_attention is True
    assert report.attention == (available, mutable)
    assert report.counts == {
        "current": 1,
        "update-available": 1,
        "mutable-tag": 1,
        "unknown": 1,
        "unsupported": 0,
    }

    payload = report.to_dict()
    assert payload["total_services"] == 4
    assert [
        item["service_identifier"]
        for item in payload["updates"]
    ] == ["available", "mutable", "unknown", "current"]


def test_update_report_requires_update_collection() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="updates must be a collection",
    ):
        UpdateReport(updates="update")  # type: ignore[arg-type]


def test_update_report_requires_update_children() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="updates must contain ServiceUpdate objects",
    ):
        UpdateReport(updates=("update",))  # type: ignore[arg-type]


def test_update_report_rejects_duplicate_service_identities() -> None:
    update = make_update()

    with pytest.raises(
        ServiceLifecycleError,
        match="service updates must have unique service identifiers",
    ):
        UpdateReport(updates=(update, update))


def test_digest_only_image_reference_is_not_mutable() -> None:
    image = ImageReference.parse(
        f"registry.example/team/app@{DIGEST}"
    )

    assert image.repository == "registry.example/team/app"
    assert image.tag is None
    assert image.digest == DIGEST
    assert image.is_mutable is False
    assert image.canonical_reference == (
        f"registry.example/team/app@{DIGEST}"
    )
