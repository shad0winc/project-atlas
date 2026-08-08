"""Compatibility tests for the Service Lifecycle services package."""

from atlas.service_lifecycle import (
    ServiceDoctor,
    ServiceLifecycleService,
    ServiceUpdateService,
)
from atlas.service_lifecycle.doctor import (
    ServiceDoctor as LegacyServiceDoctor,
)
from atlas.service_lifecycle.service import (
    ServiceLifecycleService as LegacyServiceLifecycleService,
)
from atlas.service_lifecycle.services import (
    ServiceDoctor as PackagedServiceDoctor,
)
from atlas.service_lifecycle.services import (
    ServiceLifecycleService as PackagedServiceLifecycleService,
)
from atlas.service_lifecycle.services import (
    ServiceUpdateService as PackagedServiceUpdateService,
)
from atlas.service_lifecycle.update import (
    ServiceUpdateService as LegacyServiceUpdateService,
)


def test_top_level_exports_use_packaged_services() -> None:
    assert ServiceDoctor is PackagedServiceDoctor
    assert ServiceLifecycleService is PackagedServiceLifecycleService
    assert ServiceUpdateService is PackagedServiceUpdateService


def test_legacy_service_module_remains_compatible() -> None:
    assert LegacyServiceLifecycleService is PackagedServiceLifecycleService


def test_legacy_doctor_module_remains_compatible() -> None:
    assert LegacyServiceDoctor is PackagedServiceDoctor


def test_legacy_update_module_remains_compatible() -> None:
    assert LegacyServiceUpdateService is PackagedServiceUpdateService
