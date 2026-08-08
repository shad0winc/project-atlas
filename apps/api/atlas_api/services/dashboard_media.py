"""Media dashboard summary assembly."""

from __future__ import annotations

import json
from pathlib import Path

from atlas.ari import ARIError, ARIReport
from atlas.media import MediaLibrarySummary
from atlas_api.schemas.dashboard_media import (
    DashboardMediaSummaryResponse,
    MediaLibraryResponse,
)


class DashboardMediaSummaryService:
    """Read validated ARI statistics for the Portal dashboard."""

    def __init__(
        self,
        snapshot_path: Path,
    ) -> None:
        if not isinstance(snapshot_path, Path):
            raise TypeError(
                "snapshot_path must be a Path"
            )

        self._snapshot_path = snapshot_path.expanduser()

    def read_summary(
        self,
    ) -> DashboardMediaSummaryResponse:
        """Return the latest media-library summary."""

        summary = self._read_media_summary()

        return DashboardMediaSummaryResponse(
            generated_at=summary.generated_at,
            libraries=tuple(
                MediaLibraryResponse(
                    **library.to_dict()
                )
                for library in summary.libraries
            ),
        )

    def _read_media_summary(
        self,
    ) -> MediaLibrarySummary:
        try:
            payload = json.loads(
                self._snapshot_path.read_text(
                    encoding="utf-8"
                )
            )
            report = ARIReport.from_dict(payload)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ARIError,
            ValueError,
        ) as error:
            return MediaLibrarySummary.unavailable(
                detail=(
                    "Unable to read the latest ARI snapshot: "
                    f"{type(error).__name__}"
                )
            )

        return MediaLibrarySummary.from_ari_report(
            report
        )
