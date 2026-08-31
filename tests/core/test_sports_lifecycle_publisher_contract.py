from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "modules" / "sports" / "src" / "controller.py"


def test_sports_controller_imports_lifecycle_event_publisher() -> None:
    source = CONTROLLER.read_text(encoding="utf-8")

    assert "from atlas.events import publish_event" in source
    assert source.count("publish_event(") >= 2
