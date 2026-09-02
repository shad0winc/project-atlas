from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROVIDER = ROOT / "modules/sports/src/providers/thesportsdb.py"


def test_shared_cooldown_uses_atomic_state_artifact() -> None:
    source = PROVIDER.read_text(encoding="utf-8")
    assert "SPORTS_PROVIDER_REQUEST_BUDGET_FILE" in source
    assert "retry_until_epoch" in source
    assert "fcntl.flock(" in source
    assert "fcntl.LOCK_EX" in source
    assert "temporary.replace(_PROVIDER_BUDGET_FILE)" in source


def test_request_path_checks_shared_cooldown_before_upstream() -> None:
    source = PROVIDER.read_text(encoding="utf-8")
    check_index = source.index("shared_retry_after = _shared_retry_after_seconds()")
    upstream_index = source.index("urllib.request.urlopen(")
    assert check_index < upstream_index


def test_http_429_publishes_shared_cooldown() -> None:
    source = PROVIDER.read_text(encoding="utf-8")
    assert "_write_shared_rate_limit_until(" in source
    assert "time.time() + retry_after" in source
