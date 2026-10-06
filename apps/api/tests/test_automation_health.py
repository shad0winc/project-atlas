"""Observations must be bounded, sanitized, truthful and free of state writes."""
from datetime import datetime, timezone
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from atlas_api.services.automation_health import read_automation_health

NOW = datetime(2026, 10, 6, 20, 0, tzinfo=timezone.utc)


class AutomationHealthTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.registry = self.root / "requests.json"
        self.snapshot = self.root / "scheduler.json"
        self.env = dict(ATLAS_REQUESTS_DIR=str(self.root),
                        ATLAS_DASHBOARD_SCHEDULER_SNAPSHOT_PATH=str(self.snapshot),
                        ATLAS_SUBMISSION_RECOVERY_ENABLED="1", ATLAS_ACQUISITION_ROUTING_ENABLED="0")
        self.document = dict(schema_version=2, requests={"private-user": {"title": "private-title"}},
                             submissions={"one": {"phase": "POST_STARTED"}, "two": {"phase": "RECEIPT_OBSERVED"}, "three": {"phase": "BOUND"}},
                             submission_outbox={"a": {"delivered": False}, "b": {"delivered": True}})
        self.scheduler = dict(schema_version=1, generated_at="2026-10-06T19:59:59Z", tasks=[dict(
            name="requests.reconcile", status="healthy", last_success="2026-10-06T19:59:00Z",
            consecutive_failures=0, last_error="SECRET-URL-TOKEN")])
        self.write()

    def write(self):
        self.registry.write_text(json.dumps(self.document))
        self.snapshot.write_text(json.dumps(self.scheduler))

    def report(self):
        return read_automation_health(self.env, now=NOW)

    def test_counts_and_flags_do_not_claim_recovery_proof_or_leak_or_mutate(self):
        before = [path.read_bytes() for path in (self.registry, self.snapshot)]
        report = self.report()
        self.assertEqual(report["request_registry"]["unresolved_submission_count"], 2)
        self.assertEqual(report["request_registry"]["observed_receipt_count"], 1)
        self.assertEqual(report["request_registry"]["pending_event_count"], 1)
        self.assertEqual(report["api_configuration"]["acquisition_routing"], "disabled")
        self.assertEqual(report["request_reconciliation"]["status"], "healthy")
        for private in ("private-user", "private-title", "SECRET-URL-TOKEN", str(self.root)):
            self.assertNotIn(private, json.dumps(report))
        self.assertEqual(before, [path.read_bytes() for path in (self.registry, self.snapshot)])

    def test_stale_snapshot_and_stale_success_are_separate_from_health(self):
        for field in ("generated_at", "last_success"):
            with self.subTest(field=field):
                target = self.scheduler if field == "generated_at" else self.scheduler["tasks"][0]
                original = target[field]
                target[field] = "2026-10-06T19:00:00Z"
                self.write()
                self.assertEqual(self.report()["request_reconciliation"]["status"], "stale")
                target[field] = original

    def test_failed_task_does_not_become_healthy_from_recent_success(self):
        self.scheduler["tasks"][0]["consecutive_failures"] = 1
        self.write()
        self.assertEqual(self.report()["request_reconciliation"]["status"], "attention")

    def test_native_degraded_and_disabled_tasks_require_attention(self):
        self.scheduler["tasks"][0]["status"] = "degraded"
        self.write()
        self.assertEqual(self.report()["request_reconciliation"]["status"], "attention")
        self.scheduler["tasks"][0]["status"] = "healthy"
        self.scheduler["tasks"][0]["enabled"] = False
        self.write()
        self.assertEqual(self.report()["request_reconciliation"]["status"], "attention")

    def test_missing_malformed_symlink_and_oversize_are_unavailable(self):
        self.registry.unlink()
        self.assertEqual(self.report()["request_registry"], {"status": "unavailable"})
        self.registry.symlink_to(self.snapshot)
        self.assertEqual(self.report()["request_registry"], {"status": "unavailable"})
        self.registry.unlink()
        self.registry.write_text('{"private":')
        self.assertEqual(self.report()["request_registry"], {"status": "unavailable"})
        with patch("atlas_api.services.automation_health.MAX_BYTES", 1):
            self.assertEqual(self.report()["request_reconciliation"], {"status": "unavailable"})

    def test_unknown_schema_phase_flags_and_future_timestamp_fail_closed(self):
        self.document["schema_version"] = 3
        self.env["ATLAS_SUBMISSION_RECOVERY_ENABLED"] = "yes"
        self.scheduler["generated_at"] = "2026-10-06T20:00:01Z"
        self.write()
        report = self.report()
        self.assertEqual(report["request_registry"]["status"], "unavailable")
        self.assertEqual(report["api_configuration"]["receipt_recovery"], "invalid")
        self.assertEqual(report["request_reconciliation"]["status"], "unavailable")
        self.document["schema_version"] = 2
        self.document["submissions"]["one"]["phase"] = "SECRET"
        self.write()
        self.assertEqual(self.report()["request_registry"]["status"], "unavailable")

    def test_schema1_observation_does_not_invent_empty_recovery_journals(self):
        self.document = dict(schema_version=1, requests={})
        self.write()
        self.assertEqual(self.report()["request_registry"], dict(status="observed", schema_version=1, request_count=0))
