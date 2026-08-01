"""Atlas Service Lifecycle domain.

The Service Lifecycle domain provides normalized, provider-independent
contracts for discovering, inspecting, and safely managing Atlas-operated
infrastructure services.
"""

from .models import (
    ManagedService,
    ServiceLifecycleError,
)

__all__ = [
    "ManagedService",
    "ServiceLifecycleError",
]
