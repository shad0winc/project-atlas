from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"


def deployment_source() -> str:
    return DEPLOYMENT.read_text(encoding="utf-8")


def adoption_body() -> str:
    source = deployment_source()
    start_marker = "atlas_deployment_adopt_notifications() {"

    assert source.count(start_marker) == 1, (
        "A single managed Notifications adoption function is required"
    )

    start = source.index(start_marker)
    following = re.search(
        r"(?m)^[A-Za-z_][A-Za-z_0-9]*\(\) \{",
        source[start + len(start_marker):],
    )

    assert following is not None, (
        "Adoption must be a bounded deployment function"
    )

    end = start + len(start_marker) + following.start()
    return source[start:end]


def test_adoption_is_exposed_through_existing_deployment_command() -> None:
    source = deployment_source()
    body = adoption_body()

    assert re.search(
        r"(?m)^\s*adopt-notifications\)",
        source[source.index("atlas_command_deployment() {"):],
    ), "The existing deployment command must route adopt-notifications"

    assert "atlas_deployment_adopt_notifications" in source[
        source.index("atlas_command_deployment() {"):
    ]

    assert "atlas_deployment_acquire_lock" in body
    assert "atlas_deployment_release_lock" in body


def test_lock_precedes_recovery_evidence_and_baseline_publication() -> None:
    body = adoption_body()

    lock = body.index("atlas_deployment_acquire_lock")
    capture = body.index(
        "atlas_deployment_capture_notifications_adoption_evidence"
    )
    verifications = [
        match.start()
        for match in re.finditer(
            "atlas_deployment_verify_runtime", body
        )
    ]
    publish = body.index("atlas_deployment_set_current")

    assert len(verifications) >= 2, (
        "Adoption must verify the previous runtime and the new record"
    )
    assert lock < verifications[0] < capture < verifications[-1] < publish, (
        "The deployment lock must cover both runtime verifications, "
        "recovery evidence capture, and authoritative publication"
    )


def test_adoption_preserves_the_worker_without_running_compose() -> None:
    body = adoption_body()

    assert "atlas_deployment_notifications_live_worker_row" in body
    assert "atlas_deployment_preserve_rollback_images" in body
    assert "atlas_deployment_set_status" in body
    assert "atlas_deployment_set_current" in body

    assert not re.search(
        r"\bdocker\s+(?:compose|restart|stop|start|rm|run)\b",
        body,
    ), "Adoption must not recreate, restart, or replace the live worker"


def test_adoption_requires_a_prior_verified_baseline() -> None:
    body = adoption_body()

    assert "atlas_deployment_require_current_record" in body
    assert "atlas_deployment_verify_runtime" in body
    assert "notifications_commit" in body, (
        "An already-adopted baseline must be detected and rejected"
    )
