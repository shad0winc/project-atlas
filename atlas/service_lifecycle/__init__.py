"""Atlas Service Lifecycle domain.

The Service Lifecycle domain provides normalized, provider-independent
contracts for discovering, inspecting, and safely managing Atlas-operated
infrastructure services.
"""

from .maintenance_models import (
    MaintenanceAction,
    MaintenanceRecord,
    MaintenanceReport,
    MaintenanceResult,
)
from .models import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRuntime,
)
from .doctor_models import (
    DoctorCategory,
    DoctorFinding,
    DoctorReport,
    DoctorSeverity,
)
from .update_models import (
    ImageReference,
    ServiceUpdate,
    UpdateReport,
    UpdateStatus,
)
from .services import (
    ServiceDoctor,
    ServiceLifecycleService,
    ServiceMaintenanceHistoryService,
    ServiceUpdateService,
)
from .provider import ServiceLifecycleProvider
from .providers import (
    DockerComposeProvider,
    DockerComposeProviderError,
)

__all__ = [
    "MaintenanceAction",
    "MaintenanceRecord",
    "MaintenanceReport",
    "MaintenanceResult",
    "DoctorCategory",
    "DoctorFinding",
    "DoctorReport",
    "DoctorSeverity",
    "ServiceDoctor",
    "ImageReference",
    "ServiceUpdate",
    "ServiceUpdateService",
    "UpdateReport",
    "UpdateStatus",
    "DockerComposeProvider",
    "DockerComposeProviderError",
    "ManagedService",
    "ServiceHealth",
    "ServiceHealthStatus",
    "ServiceImage",
    "ServiceLifecycleError",
    "ServiceLifecycleProvider",
    "ServiceLifecycleService",
    "ServiceMaintenanceHistoryService",
    "ServiceRuntime",
]
