"""Source contracts for the isolated API security-audit boundary."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGRESS = PROJECT_ROOT / "stack" / "ingress.yml"
DEPENDENCIES = PROJECT_ROOT / "apps" / "api" / "atlas_api" / "dependencies.py"


def test_api_receives_only_exact_runtime_event_journal() -> None:
    content = INGRESS.read_text(encoding="utf-8")

    assert (
        "/mnt/storage/configs/atlas/runtime/events.jsonl:"
        "/mnt/storage/configs/atlas/runtime/events.jsonl:rw"
    ) in content
    assert (
        "/mnt/storage/configs/atlas/runtime:"
        "/mnt/storage/configs/atlas/runtime"
    ) not in content
    assert "/mnt/storage/configs/atlas/runtime/subscribers" not in content


def test_api_has_dedicated_event_writer_supplemental_group() -> None:
    content = INGRESS.read_text(encoding="utf-8")

    assert '      - "20000"' in content
    assert '      - "20001"' in content


def test_api_security_audit_path_is_explicit() -> None:
    content = INGRESS.read_text(encoding="utf-8")

    assert (
        'ATLAS_SECURITY_AUDIT_PATH: '
        '"/mnt/storage/configs/atlas/runtime/events.jsonl"'
    ) in content


def test_security_audit_writer_is_composed_as_process_dependency() -> None:
    content = DEPENDENCIES.read_text(encoding="utf-8")

    assert "def get_security_audit_writer():" in content
    assert "SecurityAuditWriter.from_environment()" in content
