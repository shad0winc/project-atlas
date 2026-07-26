"""Public analytics contracts for Project Atlas."""

from .comparison_service import (
    AnalyticsComparisonError,
    AnalyticsComparisonService,
)
from .models import (
    AnalyticsSnapshot,
    ForecastHealth,
    ForecastSummary,
    LibraryGrowth,
    StorageSummary,
)
from .snapshot_reader import (
    ARISnapshot,
    SnapshotReader,
    SnapshotReaderError,
)

__all__ = [
    "ARISnapshot",
    "AnalyticsComparisonError",
    "AnalyticsComparisonService",
    "AnalyticsSnapshot",
    "ForecastHealth",
    "ForecastSummary",
    "LibraryGrowth",
    "SnapshotReader",
    "SnapshotReaderError",
    "StorageSummary",
]
