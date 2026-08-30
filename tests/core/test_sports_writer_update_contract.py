from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
UPDATE_SCRIPT = ROOT / "scripts/commands/update.sh"
INGRESS_COMPOSE = ROOT / "stack/ingress.yml"


def test_ingress_update_builds_private_sports_writer() -> None:
    update_source = UPDATE_SCRIPT.read_text(encoding="utf-8")
    compose_source = INGRESS_COMPOSE.read_text(encoding="utf-8")

    assert "build portal api sports-writer" in update_source
    assert "sports-writer:" in compose_source
    assert "dockerfile: modules/sports/Dockerfile.private-api" in compose_source
    assert "image: atlas-sports-writer:local" in compose_source


def test_ingress_permission_preflight_covers_private_sports_writer_context() -> None:
    update_source = UPDATE_SCRIPT.read_text(encoding="utf-8")

    for required_path in (
        "modules/sports/Dockerfile.private-api",
        "modules/sports/src/private_api.py",
        "modules/sports/src/subscriptions.py",
        "modules/sports/src/providers",
    ):
        assert required_path in update_source
