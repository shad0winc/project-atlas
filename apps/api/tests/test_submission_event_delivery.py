"""The production API factory uses the shared submission publication boundary."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from atlas.media_requests.providers.jellyseerr import JellyseerrMediaRequestProvider
from atlas.media_requests.submission_events import SubmissionEventJournalPublisher
from atlas_api.services.requests import build_default_media_requests_api_service


class APIEventDeliveryTests(unittest.TestCase):
    def test_schema_two_uses_shared_publisher_without_creating_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            registry = root / "requests.json"
            registry.write_text(json.dumps(dict(schema_version=2, requests={}, submissions={}, submission_outbox={})))
            before = registry.read_bytes()
            journal = root / "absent-events.jsonl"
            provider = JellyseerrMediaRequestProvider("http://unused.invalid", "synthetic")
            with patch.dict(os.environ, {"ATLAS_REQUESTS_DIR": folder, "ATLAS_EVENT_LOG": str(journal)}), patch(
                "atlas_api.services.requests.default_jellyseerr_media_request_provider", return_value=provider,
            ), patch("atlas_api.services.requests.RuntimeEventJournalPublisher.from_environment") as ordinary:
                application = build_default_media_requests_api_service()
                publisher = application.requests._submission_event_publisher.__self__
                self.assertIs(type(publisher), SubmissionEventJournalPublisher)
                self.assertEqual(journal, publisher.path)
                self.assertIs(application.requests._event_publisher, ordinary.return_value.publish)
            self.assertEqual(before, registry.read_bytes())
            self.assertFalse(journal.exists())
