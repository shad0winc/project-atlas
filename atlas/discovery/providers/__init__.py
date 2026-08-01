"""Concrete Discovery provider implementations.

Provider-independent contracts remain in :mod:`atlas.discovery.provider`.
Concrete adapters for external discovery systems are exported from this
package as they are introduced.
"""

from .base import (
    BaseDiscoveryProvider,
    DiscoveryProviderError,
)

__all__ = [
    "BaseDiscoveryProvider",
    "DiscoveryProviderError",
]
