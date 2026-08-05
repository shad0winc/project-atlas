"""Atlas Service Lifecycle domain.

The Service Lifecycle domain provides normalized, provider-independent
contracts for discovering, inspecting, and safely managing Atlas-operated
infrastructure services.
"""

from .recovery_models import (
    ServiceRecoveryObservation,
    ServiceRecoveryResult,
    ServiceRecoveryStatus,
)

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
    "ServiceRecoveryObservation",
    "ServiceRecoveryResult",
    "ServiceRecoveryStatus",
    "ServiceRuntime",
]

from .startup_models import (
    ServiceStartupContract,
    ServiceStartupDependency,
    StartupDependencyCondition,
)

from .startup_policy_models import (
    StartupPolicyFinding,
    StartupPolicyReport,
    StartupPolicySeverity,
)

from .startup_policy import StartupPolicyEvaluator
from .services.startup_policy import ServiceStartupPolicyService
