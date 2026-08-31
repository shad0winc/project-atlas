from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPORTS_COMPOSE = ROOT / "modules" / "sports" / "docker-compose.yml"
EVENT_LOG = "/mnt/storage/configs/atlas/runtime/events.jsonl"


def _controller_block() -> str:
    content = SPORTS_COMPOSE.read_text(encoding="utf-8")
    start = content.index("  atlas-sports-controller:")
    end = content.index("\nnetworks:\n", start)
    return content[start:end]


def test_sports_controller_has_narrow_event_writer_capability() -> None:
    controller = _controller_block()

    assert f"{EVENT_LOG}:{EVENT_LOG}" in controller
    assert f"{EVENT_LOG}:{EVENT_LOG}:ro" not in controller
    assert 'group_add:\n      - "20000"' in controller


def test_sports_controller_does_not_mount_atlas_runtime_directory() -> None:
    controller = _controller_block()

    assert "/mnt/storage/configs/atlas/runtime:/mnt/storage/configs/atlas/runtime" not in controller
