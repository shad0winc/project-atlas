"""Atlas Service Lifecycle domain.

The Service Lifecycle domain provides normalized, provider-independent
contracts for discovering, inspecting, and safely managing Atlas-operated
infrastructure services.
"""

from .models import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRuntime,
)
from .provider import ServiceLifecycleProvider
from .service import ServiceLifecycleService
from .providers import (
    DockerComposeProvider,
    DockerComposeProviderError,
)

__all__ = [
    "DockerComposeProvider",
    "DockerComposeProviderError",
    "ManagedService",
    "ServiceHealth",
    "ServiceHealthStatus",
    "ServiceImage",
    "ServiceLifecycleError",
    "ServiceLifecycleProvider",
    "ServiceLifecycleService",
    "ServiceRuntime",
]
