from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFY = ROOT / "scripts" / "verify-ingress.sh"
UPDATE = ROOT / "scripts" / "commands" / "update.sh"


def test_ingress_verifier_requires_sports_writer_runtime_health() -> None:
    source = VERIFY.read_text(encoding="utf-8")

    start = source.index("for container in \\\n")
    end = source.index("\ndo\n", start)
    block = source[start:end]

    assert "atlas-caddy" in block
    assert "atlas-api" in block
    assert "atlas-portal" in block
    assert "atlas-sports-writer" in block

    loop = source[start:source.index("\ndone", end)]
    assert 'pass "$container container present"' in loop
    assert '"$container running"' in loop
    assert '"$container healthy"' in loop


def test_update_readiness_requires_sports_writer() -> None:
    source = UPDATE.read_text(encoding="utf-8")

    start = source.index(
        "atlas_update_wait_for_ingress_readiness()"
    )
    end = source.index(
        "\natlas_update_ingress_container_state()",
        start,
    )
    block = source[start:end]

    assert "atlas-api" in block
    assert "atlas-portal" in block
    assert "atlas-caddy" in block
    assert "atlas-sports-writer" in block
    assert "status" in block
    assert "health" in block
    assert "unhealthy|missing|''" in block
