"""Tests for the read-only Atlas system collector."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.operations import (
    OperationsSectionId,
    OperationsStatus,
)
from atlas.operations.collectors import (
    SystemCollector,
)


class FakeSystemProvider:
    """Deterministic provider used by collector tests."""

    def hostname(self) -> str:
        return " docker "

    def operating_system(self) -> str:
        return " Debian GNU/Linux 13 "

    def kernel_release(self) -> str:
        return " 6.14.11-4-pve "

    def uptime_seconds(self) -> float:
        return 183845.5

    def cpu_count(self) -> int:
        return 16

    def cpu_model(self) -> str:
        return " Intel Test CPU "

    def memory_bytes(self) -> tuple[int, int, int]:
        gib = 1024**3

        return (
            24 * gib,
            6 * gib,
            18 * gib,
        )


class FailingSystemProvider:
    """Provider with every source unavailable."""

    def hostname(self) -> str:
        raise OSError("hostname unavailable")

    def operating_system(self) -> str:
        raise OSError("os-release unavailable")

    def kernel_release(self) -> str:
        raise OSError("kernel unavailable")

    def uptime_seconds(self) -> float:
        raise OSError("uptime unavailable")

    def cpu_count(self) -> int:
        raise OSError("CPU count unavailable")

    def cpu_model(self) -> str:
        raise OSError("CPU model unavailable")

    def memory_bytes(self) -> tuple[int, int, int]:
        raise OSError("memory unavailable")


def system_collector(
    provider: object | None = None,
) -> SystemCollector:
    return SystemCollector(
        provider=(
            provider
            if provider is not None
            else FakeSystemProvider()
        ),
    )


def test_system_collector_metadata() -> None:
    result = system_collector()

    assert result.section_id is OperationsSectionId.SYSTEM
    assert result.name == "System"
    assert result.timeout_seconds == 10.0
    assert result.description == (
        "Host operating-system and resource information"
    )


def test_system_collector_returns_canonical_section() -> None:
    section = system_collector().collect_checked()

    assert section.identifier is OperationsSectionId.SYSTEM
    assert section.name == "System"
    assert len(section.findings) == 6


def test_system_collector_finding_order_is_deterministic() -> None:
    section = system_collector().collect()

    assert tuple(
        finding.identifier
        for finding in section.findings
    ) == (
        "system.hostname",
        "system.operating-system",
        "system.kernel",
        "system.uptime",
        "system.cpu",
        "system.memory",
    )


def test_system_collector_normalizes_text_sources() -> None:
    section = system_collector().collect()

    hostname = section.findings[0]
    operating_system = section.findings[1]
    kernel = section.findings[2]

    assert hostname.metadata["value"] == "docker"
    assert operating_system.metadata["value"] == (
        "Debian GNU/Linux 13"
    )
    assert kernel.metadata["value"] == "6.14.11-4-pve"


def test_system_collector_collects_uptime() -> None:
    finding = system_collector().collect().findings[3]

    assert finding.status is OperationsStatus.HEALTHY
    assert finding.metadata["seconds"] == 183845.5
    assert finding.message == (
        "System uptime: 2d 3h 4m 5s"
    )


def test_system_collector_collects_cpu() -> None:
    finding = system_collector().collect().findings[4]

    assert finding.status is OperationsStatus.HEALTHY
    assert finding.metadata == {
        "logical_count": 16,
        "model": "Intel Test CPU",
    }
    assert finding.message == (
        "Intel Test CPU (16 logical CPUs)"
    )


def test_system_collector_collects_memory() -> None:
    finding = system_collector().collect().findings[5]
    gib = 1024**3

    assert finding.status is OperationsStatus.HEALTHY
    assert finding.metadata == {
        "available_bytes": 18 * gib,
        "percent_used": 25.0,
        "total_bytes": 24 * gib,
        "used_bytes": 6 * gib,
    }
    assert finding.message == "Memory usage: 25.00%"


def test_system_collector_is_immutable() -> None:
    result = system_collector()

    with pytest.raises(FrozenInstanceError):
        result.name = "Changed"  # type: ignore[misc]


def test_system_collector_degrades_each_failed_source() -> None:
    section = system_collector(
        FailingSystemProvider(),
    ).collect_checked()

    assert len(section.findings) == 6

    assert all(
        finding.status is OperationsStatus.UNKNOWN
        for finding in section.findings
    )

    assert all(
        finding.action_required is False
        for finding in section.findings
    )


def test_system_collector_records_provider_errors() -> None:
    section = system_collector(
        FailingSystemProvider(),
    ).collect()

    assert section.findings[0].metadata == {
        "error": "hostname unavailable",
    }
    assert section.findings[3].metadata == {
        "error": "uptime unavailable",
    }
    assert section.findings[5].metadata == {
        "error": "memory unavailable",
    }


@pytest.mark.parametrize(
    "provider",
    (
        type(
            "InvalidUptime",
            (FakeSystemProvider,),
            {
                "uptime_seconds": lambda self: -1,
            },
        )(),
        type(
            "InvalidCpu",
            (FakeSystemProvider,),
            {
                "cpu_count": lambda self: 0,
            },
        )(),
        type(
            "InvalidMemory",
            (FakeSystemProvider,),
            {
                "memory_bytes": (
                    lambda self: (100, 80, 30)
                ),
            },
        )(),
    ),
)
def test_system_collector_degrades_invalid_values(
    provider: object,
) -> None:
    section = system_collector(provider).collect()

    assert any(
        finding.status is OperationsStatus.UNKNOWN
        for finding in section.findings
    )


def test_system_collector_rejects_wrong_section_override() -> None:
    with pytest.raises(
        ValueError,
        match="must use the system section",
    ):
        SystemCollector(
            section_id="storage",
            provider=FakeSystemProvider(),
        )


def test_public_system_collector_exports() -> None:
    from atlas.operations import collectors

    assert collectors.SystemCollector is SystemCollector
    assert collectors.HostSystemProvider is not None
    assert collectors.SystemProvider is not None


def test_host_provider_prefers_model_name_over_processor_index(
    tmp_path,
) -> None:
    from atlas.operations.collectors import HostSystemProvider

    proc_root = tmp_path / "proc"
    proc_root.mkdir()

    (proc_root / "cpuinfo").write_text(
        (
            "processor : 0\n"
            "vendor_id : GenuineIntel\n"
            "model name : Intel Core Test Processor\n"
            "processor : 1\n"
            "model name : Intel Core Test Processor\n"
        ),
        encoding="utf-8",
    )

    provider = HostSystemProvider(
        proc_root=proc_root,
        os_release_path=tmp_path / "os-release",
    )

    assert provider.cpu_model() == "Intel Core Test Processor"


def test_host_provider_does_not_use_numeric_processor_index(
    tmp_path,
    monkeypatch,
) -> None:
    from atlas.operations.collectors import HostSystemProvider
    from atlas.operations.collectors import system as system_module

    proc_root = tmp_path / "proc"
    proc_root.mkdir()

    (proc_root / "cpuinfo").write_text(
        "processor : 0\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        system_module.platform,
        "processor",
        lambda: "1",
    )

    provider = HostSystemProvider(
        proc_root=proc_root,
        os_release_path=tmp_path / "os-release",
    )

    with pytest.raises(
        ValueError,
        match="CPU model is unavailable",
    ):
        provider.cpu_model()


def test_host_provider_accepts_hardware_identity(
    tmp_path,
) -> None:
    from atlas.operations.collectors import HostSystemProvider

    proc_root = tmp_path / "proc"
    proc_root.mkdir()

    (proc_root / "cpuinfo").write_text(
        (
            "processor : 0\n"
            "Hardware : ARM Test Platform\n"
        ),
        encoding="utf-8",
    )

    provider = HostSystemProvider(
        proc_root=proc_root,
        os_release_path=tmp_path / "os-release",
    )

    assert provider.cpu_model() == "ARM Test Platform"
