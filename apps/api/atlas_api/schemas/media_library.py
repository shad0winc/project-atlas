"""Media-library detail API response contracts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict

from atlas.media import (
    MediaLibraryDetail,
    MediaLibraryDetailStatus,
    MediaLibrarySynchronization,
)


class MediaLibraryFilesystemResponse(BaseModel):
    """Filesystem information exposed for one media library."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        from_attributes=True,
    )

    path: str
    item_count: int


class MediaLibraryProviderResponse(BaseModel):
    """Provider information exposed for one media library."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        from_attributes=True,
    )

    name: str
    library_name: str
    library_type: str
    path: str
    status: str


class MediaLibraryValidationResponse(BaseModel):
    """Validation state exposed for one media library."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        from_attributes=True,
    )

    configured: bool
    path_matches: bool | None
    synchronization: MediaLibrarySynchronization


class MediaLibraryDetailResponse(BaseModel):
    """Stable read-only response for one Atlas media library."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        from_attributes=True,
    )

    id: str
    label: str
    status: MediaLibraryDetailStatus
    generated_at: str
    count: int | None
    detail: str | None = None
    filesystem: MediaLibraryFilesystemResponse | None = None
    provider: MediaLibraryProviderResponse | None = None
    validation: MediaLibraryValidationResponse

    @classmethod
    def from_domain(
        cls,
        detail: MediaLibraryDetail,
    ) -> Self:
        """Create an API response from a validated domain model."""

        if not isinstance(detail, MediaLibraryDetail):
            raise TypeError(
                "detail must be MediaLibraryDetail"
            )

        return cls.model_validate(
            detail,
            from_attributes=True,
        )
