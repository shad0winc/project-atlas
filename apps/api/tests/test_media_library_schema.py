"""Tests for media-library detail API response schemas."""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from atlas.media import (
    MediaLibraryDetail,
    MediaLibraryFilesystem,
    MediaLibraryProvider,
    MediaLibraryValidation,
)
from atlas_api.schemas.media_library import (
    MediaLibraryDetailResponse,
    MediaLibraryFilesystemResponse,
    MediaLibraryProviderResponse,
    MediaLibraryValidationResponse,
)


def _domain_detail() -> MediaLibraryDetail:
    """Return a stable validated domain object for schema tests."""

    return MediaLibraryDetail(
        id="movies",
        label="Movies",
        status="available",
        generated_at="2026-07-27T23:00:00Z",
        count=12,
        detail="Filesystem library count",
        filesystem=MediaLibraryFilesystem(
            path="/mnt/storage/media/Movies",
            item_count=12,
        ),
        provider=MediaLibraryProvider(
            name="jellyfin",
            library_name="Movies",
            library_type="movies",
            path="/media/Movies",
            status="available",
        ),
        validation=MediaLibraryValidation(
            configured=True,
            path_matches=True,
            synchronization="synchronized",
        ),
    )


class MediaLibraryChildResponseTests(
    unittest.TestCase
):
    """Verify nested response contracts."""

    def test_filesystem_response_forbids_extra_fields(
        self,
    ) -> None:
        with self.assertRaises(ValidationError):
            MediaLibraryFilesystemResponse(
                path="/mnt/storage/media/Movies",
                item_count=12,
                unexpected=True,
            )

    def test_provider_response_is_frozen(self) -> None:
        response = MediaLibraryProviderResponse(
            name="jellyfin",
            library_name="Movies",
            library_type="movies",
            path="/media/Movies",
            status="available",
        )

        with self.assertRaises(ValidationError):
            response.status = "unavailable"

    def test_validation_response_rejects_unknown_state(
        self,
    ) -> None:
        with self.assertRaises(ValidationError):
            MediaLibraryValidationResponse(
                configured=True,
                path_matches=True,
                synchronization="invalid",
            )


class MediaLibraryDetailResponseTests(
    unittest.TestCase
):
    """Verify the complete detail response contract."""

    def test_adapts_validated_domain_model(self) -> None:
        response = MediaLibraryDetailResponse.from_domain(
            _domain_detail()
        )

        self.assertEqual(
            {
                "id": "movies",
                "label": "Movies",
                "status": "available",
                "generated_at": "2026-07-27T23:00:00Z",
                "count": 12,
                "detail": "Filesystem library count",
                "filesystem": {
                    "path": "/mnt/storage/media/Movies",
                    "item_count": 12,
                },
                "provider": {
                    "name": "jellyfin",
                    "library_name": "Movies",
                    "library_type": "movies",
                    "path": "/media/Movies",
                    "status": "available",
                },
                "validation": {
                    "configured": True,
                    "path_matches": True,
                    "synchronization": "synchronized",
                },
            },
            response.model_dump(
                mode="json"
            ),
        )

    def test_nested_values_use_response_models(
        self,
    ) -> None:
        response = MediaLibraryDetailResponse.from_domain(
            _domain_detail()
        )

        self.assertIsInstance(
            response.filesystem,
            MediaLibraryFilesystemResponse,
        )
        self.assertIsInstance(
            response.provider,
            MediaLibraryProviderResponse,
        )
        self.assertIsInstance(
            response.validation,
            MediaLibraryValidationResponse,
        )

    def test_response_forbids_unknown_fields(self) -> None:
        payload = _domain_detail().to_dict()
        payload["unexpected"] = True

        with self.assertRaises(ValidationError):
            MediaLibraryDetailResponse.model_validate(
                payload
            )

    def test_response_rejects_invalid_status(self) -> None:
        payload = _domain_detail().to_dict()
        payload["status"] = "unknown"

        with self.assertRaises(ValidationError):
            MediaLibraryDetailResponse.model_validate(
                payload
            )

    def test_from_domain_rejects_unvalidated_input(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            TypeError,
            "detail must be MediaLibraryDetail",
        ):
            MediaLibraryDetailResponse.from_domain(
                {
                    "id": "movies",
                }
            )


if __name__ == "__main__":
    unittest.main()
