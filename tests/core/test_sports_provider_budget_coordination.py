from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_writer_and_controller_share_provider_budget_file() -> None:
    compose = (ROOT / "modules/sports/docker-compose.yml").read_text(encoding="utf-8")
    ingress = (ROOT / "stack/ingress.yml").read_text(encoding="utf-8")
    expected = "SPORTS_PROVIDER_REQUEST_BUDGET_FILE"
    assert expected in compose
    assert expected in ingress


def test_provider_health_publication_is_best_effort() -> None:
    worker = (ROOT / "modules/sports/src/worker.py").read_text(encoding="utf-8")
    assert "def publish_provider_health_event(" in worker
    assert "Unable to publish" in worker
    assert "publish_provider_health_event(" in worker
