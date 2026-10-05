"""Full-checkout scheduler integration: opt-in, receipt-only recovery and replay."""
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from atlas.media_requests.construction import build_request_service
from atlas.media_requests.models import MediaRequest
from atlas.media_requests.providers.jellyseerr import JellyseerrMediaRequestProvider
from atlas.media_requests.providers.managed_profiles import ManagedProfileEvidence
from atlas.media_requests.reconciler import ReconciliationOutcome
from atlas.media_requests.service import MediaRequestService
from atlas.media_requests.repository import JsonMediaRequestRepository
from atlas.media_requests.submission_recovery import SubmissionRecoveryRepository
from atlas.media_requests import scheduled_reconcile as scheduled

EMPTY = ReconciliationOutcome(0, 0, 0, 0, ())
STAMP = "2026-10-05T00:00:00Z"


def provider():
    return JellyseerrMediaRequestProvider("http://unused.invalid", "synthetic",
        movie_server_id=0, tv_server_id=0,
        audio_profile_ids={("movie", "english_required"): 8},
        managed_profile_reader=lambda row, server: ManagedProfileEvidence(row.media_type.value, server, int(row.provider_media_id), 42, 8))


def service(tmp_path, monkeypatch):
    journal = tmp_path / "events.jsonl"
    journal.touch(mode=0o640)
    monkeypatch.setenv("ATLAS_EVENT_LOG", str(journal))
    return build_request_service(SubmissionRecoveryRepository(tmp_path / "requests"), [provider()]), journal


def prepare(value, *, receipt=True, request_id="fixture"):
    row = value.create_request(MediaRequest(request_id=request_id, user_id="viewer", media_type="movie",
        provider="jellyseerr", provider_media_id="123", title="Synthetic", audio_preference="english_required", created_at=STAMP))
    intent, attempt = value.repository.begin_submission(row, server=0, profile=8, started_at=STAMP)
    if receipt:
        value.repository.observe_receipt(intent, attempt, 9)


def dependencies(monkeypatch):
    monkeypatch.setattr(scheduled, "default_jellyfin_provider", lambda: object())
    monkeypatch.setattr(scheduled, "JellyfinRequestReadiness", lambda _: object())
    monkeypatch.setattr(scheduled, "reconcile_active_requests", lambda *args, **kwargs: EMPTY)


def test_default_off_preserves_schema_two_receipts_and_outbox(tmp_path, monkeypatch):
    value, journal = service(tmp_path, monkeypatch)
    prepare(value)
    raw = value.repository.registry_file.read_bytes()
    monkeypatch.delenv("ATLAS_SUBMISSION_RECOVERY_ENABLED", raising=False)
    dependencies(monkeypatch)
    with patch.object(value, "recover_submission") as recover, patch.object(value, "drain_submission_events") as drain:
        assert scheduled.run_reconciliation(service_factory=lambda: value) == EMPTY
    recover.assert_not_called()
    drain.assert_not_called()
    assert value.repository.registry_file.read_bytes() == raw
    assert journal.read_bytes() == b""


@pytest.mark.parametrize("flag", ["", "true", "yes", "2", "false"])
def test_invalid_opt_in_fails_before_service_construction(flag, monkeypatch):
    monkeypatch.setenv("ATLAS_SUBMISSION_RECOVERY_ENABLED", flag)
    with patch.object(scheduled, "build_default_service") as factory:
        with pytest.raises(ValueError, match="0 or 1"):
            scheduled.run_reconciliation(service_factory=factory)
    factory.assert_not_called()


def test_enabled_schema_one_fails_before_readiness_or_mutation(tmp_path, monkeypatch):
    repository = JsonMediaRequestRepository(tmp_path)
    row = MediaRequest(request_id="legacy", user_id="viewer", media_type="movie",
        provider="jellyseerr", provider_media_id="123", title="Synthetic")
    repository.save(row)
    raw = repository.registry_file.read_bytes()
    value = MediaRequestService(repository, [provider()])
    monkeypatch.setenv("ATLAS_SUBMISSION_RECOVERY_ENABLED", "1")
    with patch.object(scheduled, "default_jellyfin_provider") as readiness:
        with pytest.raises(ValueError, match="schema-2"):
            scheduled.run_reconciliation(service_factory=lambda: value)
    readiness.assert_not_called()
    assert repository.registry_file.read_bytes() == raw


def test_receipt_get_binding_and_durable_outbox_precede_normal_refresh(tmp_path, monkeypatch):
    value, journal = service(tmp_path, monkeypatch)
    prepare(value)
    monkeypatch.setenv("ATLAS_SUBMISSION_RECOVERY_ENABLED", "1")
    dependencies(monkeypatch)
    backend = dict(id=9, type="movie", is4k=False, serverId=0, profileId=8, status=2,
        media=dict(tmdbId=123, mediaType="movie", status=3), createdAt=STAMP, updatedAt=STAMP)
    def refresh(*args, **kwargs):
        assert value.repository.get_attempt("fixture").phase == "BOUND"
        assert value.repository.pending_submission_events() == {}
        assert len(journal.read_bytes().splitlines()) == 2
        return EMPTY
    monkeypatch.setattr(scheduled, "reconcile_active_requests", refresh)
    with patch.object(JellyseerrMediaRequestProvider, "_recovery_json", return_value=backend) as transport, patch.object(
        JellyseerrMediaRequestProvider, "submit_with_receipt") as post:
        outcome = scheduled.run_reconciliation(service_factory=lambda: value)
    post.assert_not_called()
    assert transport.call_count == 1 and transport.call_args.args[0] == "GET"
    assert outcome.receipts.recovered == 1
    assert (outcome.events_attempted, outcome.events_delivered, outcome.events_pending) == (2, 2, 0)
    record_bytes = journal.read_bytes()
    with patch.object(JellyseerrMediaRequestProvider, "_recovery_json") as transport:
        again = scheduled.run_reconciliation(service_factory=lambda: value)
    transport.assert_not_called()
    assert again.events_delivered == 0
    assert journal.read_bytes() == record_bytes
    summary = json.loads(scheduled.render_result(outcome))
    assert summary["submission_recovery"]["receipts"]["recovered"] == 1
    assert summary["submission_recovery"]["events_delivered"] == 2


def test_unknown_receipt_barrier_survives_enabled_callback(tmp_path, monkeypatch):
    value, journal = service(tmp_path, monkeypatch)
    prepare(value, receipt=False)
    raw = value.repository.registry_file.read_bytes()
    monkeypatch.setenv("ATLAS_SUBMISSION_RECOVERY_ENABLED", "1")
    dependencies(monkeypatch)
    with patch.object(JellyseerrMediaRequestProvider, "_recovery_json") as transport, patch.object(
        JellyseerrMediaRequestProvider, "submit_with_receipt") as post:
        outcome = scheduled.run_reconciliation(service_factory=lambda: value)
    assert outcome.receipts.needs_correlation == 1
    transport.assert_not_called()
    post.assert_not_called()
    assert value.repository.registry_file.read_bytes() == raw
    assert journal.read_bytes() == b""


def test_recovery_infrastructure_error_is_sanitized(tmp_path, monkeypatch):
    value, journal = service(tmp_path, monkeypatch)
    monkeypatch.setenv("ATLAS_SUBMISSION_RECOVERY_ENABLED", "1")
    dependencies(monkeypatch)
    output, errors = StringIO(), StringIO()
    with patch.object(scheduled, "reconcile_submission_receipts", side_effect=RuntimeError("synthetic-private-value")):
        assert scheduled.main([], service_factory=lambda: value, stdout=output, stderr=errors) == 1
    assert output.getvalue() == ""
    assert "synthetic-private-value" not in errors.getvalue()
    assert "remains unverified" in errors.getvalue()


def test_scheduler_uses_separate_bounded_rotating_budgets(tmp_path, monkeypatch):
    value, journal = service(tmp_path, monkeypatch)
    monkeypatch.setenv("ATLAS_SUBMISSION_RECOVERY_ENABLED", "1")
    dependencies(monkeypatch)
    instant = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
    minute = int(instant.timestamp()) // 60
    with patch.object(scheduled, "datetime") as clock, patch.object(
        scheduled, "reconcile_submission_receipts", wraps=scheduled.reconcile_submission_receipts) as receipts, patch.object(
        value, "drain_submission_events", wraps=value.drain_submission_events) as events:
        clock.now.return_value = instant
        outcome = scheduled.run_reconciliation(service_factory=lambda: value)
    receipts.assert_called_once_with(value, limit=10, offset=minute * 10)
    events.assert_called_once_with(limit=25, offset=minute * 25)
    assert outcome.events_attempted == 0
    assert journal.read_bytes() == b""
