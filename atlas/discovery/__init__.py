"""
Atlas Discovery

The Discovery domain provides a normalized view of external media discovery
providers. It defines provider-independent models and services that can be used
to discover, evaluate, and report on media indexers and related capabilities.
"""

from .models import (
    DiscoveryCapability,
    DiscoveryHealth,
    DiscoveryIndexer,
)

from .provider import DiscoveryProvider
from .report import DiscoveryReport
from .service import DiscoveryService

__all__ = [
    "DiscoveryCapability",
    "DiscoveryHealth",
    "DiscoveryIndexer",
    "DiscoveryProvider",
    "DiscoveryReport",
    "DiscoveryService",
]
