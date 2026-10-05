"""API default construction follows the same persisted request schema."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlas.media_requests.providers.jellyseerr import JellyseerrMediaRequestProvider
from atlas.media_requests.service import MediaRequestService
from atlas.media_requests.submission_recovery import SubmissionRecoveryService
from atlas_api.services.requests import build_default_media_requests_api_service, MediaRequestsUnavailableError


class APIRequestSchemaTests(unittest.TestCase):
    def test_api_selects_matching_service_without_changing_state(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / "requests.json"
            provider = JellyseerrMediaRequestProvider("http://unused.invalid", "synthetic")
            for schema in (1, 2):
                registry.write_text(json.dumps(dict(schema_version=schema, requests={}, **(
                    {"submissions": {}, "submission_outbox": {}} if schema == 2 else {}))))
                before = registry.read_bytes()
                with patch.dict(os.environ, {"ATLAS_REQUESTS_DIR": folder}), patch(
                    "atlas_api.services.requests.default_jellyseerr_media_request_provider", return_value=provider,
                ), patch("atlas_api.services.requests.RuntimeEventJournalPublisher.from_environment") as publisher:
                    application = build_default_media_requests_api_service()
                    self.assertIs(type(application.requests), SubmissionRecoveryService if schema == 2 else MediaRequestService)
                    self.assertIs(application.repository, application.requests.repository)
                    self.assertIs(application.requests._event_publisher, publisher.return_value.publish)
                self.assertEqual(registry.read_bytes(), before)
                self.assertEqual(set(Path(folder).iterdir()), {registry})

    def test_invalid_schema_is_sanitized_and_does_not_build_provider(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = Path(folder) / "requests.json"
            registry.write_text('{"schema_version": 99, "requests": {}}')
            before = registry.read_bytes()
            with patch.dict(os.environ, {"ATLAS_REQUESTS_DIR": folder}), patch(
                "atlas_api.services.requests.default_jellyseerr_media_request_provider",
            ) as provider:
                with self.assertRaises(MediaRequestsUnavailableError):
                    build_default_media_requests_api_service()
                provider.assert_not_called()
            self.assertEqual(registry.read_bytes(), before)
