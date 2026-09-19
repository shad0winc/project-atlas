from __future__ import annotations

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT = ROOT / "scripts/commands/deployment.sh"


def function_body(name: str) -> str:
    source = DEPLOYMENT.read_text(encoding="utf-8")
    definitions = list(
        re.finditer(
            r"(?m)^([A-Za-z_][A-Za-z_0-9]*)\(\)\s*"
            r"(?:\{|\()\s*$",
            source,
        )
    )
    matches = [
        index
        for index, match in enumerate(definitions)
        if match.group(1) == name
    ]
    assert len(matches) == 1, (name, matches)
    index = matches[0]
    start = definitions[index].start()
    end = (
        definitions[index + 1].start()
        if index + 1 < len(definitions)
        else len(source)
    )
    return source[start:end]


def test_rollback_verifies_adopted_previous_runtime() -> None:
    body = function_body(
        "atlas_deployment_verify_rollback_runtime"
    )

    # The rollback verifier must attest the previous baseline using
    # the same image/source contract as ordinary runtime verification.
    # This assertion does not require recreating the Notifications
    # worker or deploying a managed source generation.
    assert "atlas_deployment_verify_runtime" in body


def test_failed_rollback_reconciliation_retains_notifications() -> None:
    body = function_body(
        "atlas_deployment_publish_reconciliation_baseline"
    )

    assert "notifications_commit" in body
    assert "notifications_commit=$notifications_commit" in body

    for name in (
        "notifications-source.tar.gz",
        "notifications-image.tsv",
        "notifications-source-commit",
    ):
        assert name in body, name

    # The recovery evidence must be present before the temporary
    # record is verified and published.
    assert body.index(
        "notifications-source-commit"
    ) < body.index(
        'atlas_deployment_verify_runtime "$temporary"'
    )

    assert "MANIFEST.sha256" in body


def test_failed_after_apply_reconciliation_retains_notifications() -> None:
    body = function_body(
        "atlas_deployment_recover_failed_after_apply"
    )

    assert "notifications_commit" in body
    assert "notifications_commit=$notifications_commit" in body

    for name in (
        "notifications-source.tar.gz",
        "notifications-image.tsv",
        "notifications-source-commit",
    ):
        assert name in body, name

    assert body.index(
        "notifications-source-commit"
    ) < body.index(
        'atlas_deployment_verify_runtime "$temporary"'
    )

    assert "MANIFEST.sha256" in body
