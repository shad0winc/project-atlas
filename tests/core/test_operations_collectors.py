"""Tests for the Atlas Operations collector base contract."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.operations import (
    OperationsSection,
    OperationsSectionId,
)
from atlas.operations.collectors import (
    OperationsCollector,
    OperationsCollectorContractError,
    OperationsCollectorError,
    OperationsCollectorTimeoutError,
)


class StubCollector(OperationsCollector):
    """Collector returning its configured section."""

    def collect(self) -> OperationsSection:
        return OperationsSection(
            identifier=self.section_id,
            name=self.name,
            description=self.description,
        )


class WrongSectionCollector(OperationsCollector):
    """Collector deliberately violating its section contract."""

    def collect(self) -> OperationsSection:
        return OperationsSection(
            identifier="storage",
            name="Storage",
        )


class InvalidResultCollector(OperationsCollector):
    """Collector deliberately returning the wrong type."""

    def collect(self) -> OperationsSection:
        return "invalid"  # type: ignore[return-value]


class FailingCollector(OperationsCollector):
    """Collector raising an unexpected provider exception."""

    def collect(self) -> OperationsSection:
        raise ValueError("provider unavailable")


class KnownFailureCollector(OperationsCollector):
    """Collector raising a normalized collector error."""

    def collect(self) -> OperationsSection:
        raise OperationsCollectorTimeoutError(
            "collector timed out",
        )


def collector(**overrides: object) -> StubCollector:
    values: dict[str, object] = {
        "section_id": "system",
        "name": "System",
        "timeout_seconds": 10,
        "description": "Host operating-system information",
    }
    values.update(overrides)

    return StubCollector(**values)  # type: ignore[arg-type]


def test_abstract_collector_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        OperationsCollector(  # type: ignore[abstract]
            section_id="system",
            name="System",
        )


def test_collector_normalizes_metadata() -> None:
    result = collector(
        section_id=" SYSTEM ",
        name=" System Collector ",
        timeout_seconds=5,
        description=" Host information ",
    )

    assert result.section_id is OperationsSectionId.SYSTEM
    assert result.name == "System Collector"
    assert result.timeout_seconds == 5.0
    assert result.description == "Host information"


def test_collector_accepts_enum_section_identity() -> None:
    result = collector(
        section_id=OperationsSectionId.STORAGE,
    )

    assert result.section_id is OperationsSectionId.STORAGE


def test_collector_serialization_is_deterministic() -> None:
    result = collector()

    assert result.to_dict() == {
        "section_id": "system",
        "name": "System",
        "description": "Host operating-system information",
        "timeout_seconds": 10.0,
    }


def test_collect_checked_returns_valid_section() -> None:
    result = collector().collect_checked()

    assert isinstance(result, OperationsSection)
    assert result.identifier is OperationsSectionId.SYSTEM
    assert result.name == "System"


@pytest.mark.parametrize(
    "section_id",
    (
        "",
        "not-a-section",
        123,
    ),
)
def test_collector_rejects_invalid_section_identity(
    section_id: object,
) -> None:
    with pytest.raises(OperationsCollectorContractError):
        collector(section_id=section_id)


@pytest.mark.parametrize(
    "name",
    (
        "",
        " ",
        None,
    ),
)
def test_collector_rejects_invalid_name(
    name: object,
) -> None:
    with pytest.raises(OperationsCollectorContractError):
        collector(name=name)


@pytest.mark.parametrize(
    "timeout",
    (
        0,
        -1,
        True,
        "10",
        float("inf"),
        float("-inf"),
        float("nan"),
    ),
)
def test_collector_rejects_invalid_timeout(
    timeout: object,
) -> None:
    with pytest.raises(OperationsCollectorContractError):
        collector(timeout_seconds=timeout)


def test_collector_rejects_blank_description() -> None:
    with pytest.raises(OperationsCollectorContractError):
        collector(description=" ")


def test_collect_checked_rejects_wrong_result_type() -> None:
    result = InvalidResultCollector(
        section_id="system",
        name="System",
    )

    with pytest.raises(
        OperationsCollectorContractError,
        match="must return an OperationsSection",
    ):
        result.collect_checked()


def test_collect_checked_rejects_wrong_section() -> None:
    result = WrongSectionCollector(
        section_id="system",
        name="System",
    )

    with pytest.raises(
        OperationsCollectorContractError,
        match="wrong section identity",
    ):
        result.collect_checked()


def test_collect_checked_wraps_unexpected_errors() -> None:
    result = FailingCollector(
        section_id="system",
        name="System",
    )

    with pytest.raises(
        OperationsCollectorError,
        match="system collector failed: provider unavailable",
    ) as exc_info:
        result.collect_checked()

    assert isinstance(exc_info.value.__cause__, ValueError)


def test_collect_checked_preserves_collector_errors() -> None:
    result = KnownFailureCollector(
        section_id="system",
        name="System",
    )

    with pytest.raises(
        OperationsCollectorTimeoutError,
        match="collector timed out",
    ):
        result.collect_checked()


def test_collector_is_immutable() -> None:
    result = collector()

    with pytest.raises(FrozenInstanceError):
        result.name = "Changed"  # type: ignore[misc]


def test_public_collector_exports() -> None:
    from atlas.operations import collectors

    assert collectors.OperationsCollector is OperationsCollector
    assert (
        collectors.OperationsCollectorContractError
        is OperationsCollectorContractError
    )
    assert (
        collectors.OperationsCollectorError
        is OperationsCollectorError
    )
    assert (
        collectors.OperationsCollectorTimeoutError
        is OperationsCollectorTimeoutError
    )
