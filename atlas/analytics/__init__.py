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
from .timeline import (
    AnalyticsTimeline,
    AnalyticsTimelineBuilder,
    AnalyticsTimelineError,
    TimelineGap,
)

__all__ = [
    "ARISnapshot",
    "AnalyticsComparisonError",
    "AnalyticsComparisonService",
    "AnalyticsSnapshot",
    "AnalyticsTimeline",
    "AnalyticsTimelineBuilder",
    "AnalyticsTimelineError",
    "ForecastHealth",
    "ForecastSummary",
    "LibraryGrowth",
    "SnapshotReader",
    "SnapshotReaderError",
    "StorageSummary",
    "TimelineGap",
]
