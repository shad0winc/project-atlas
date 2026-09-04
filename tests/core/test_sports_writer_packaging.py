from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRIVATE_DOCKERFILE = (
    PROJECT_ROOT / "modules" / "sports" / "Dockerfile.private-api"
)


def test_sports_writer_packages_live_tv_binding_dependency() -> None:
    content = PRIVATE_DOCKERFILE.read_text(encoding="utf-8")

    assert (
        "COPY modules/sports/src/live_tv_bindings.py "
        "/srv/sports/live_tv_bindings.py"
        in content
    )
