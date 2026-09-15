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


def test_sports_writer_packages_neutral_games_state_reader() -> None:
    content = PRIVATE_DOCKERFILE.read_text(encoding="utf-8")

    assert (
        "COPY modules/sports/src/games_state.py "
        "/srv/sports/games_state.py"
        in content
    )


def test_private_sports_api_uses_neutral_games_state_reader() -> None:
    private_api = (
        PROJECT_ROOT
        / "modules"
        / "sports"
        / "src"
        / "private_api.py"
    ).read_text(encoding="utf-8")

    assert "from games_state import load_games" in private_api
    assert "from feed import load_games" not in private_api


def test_writer_build_preflight_tracks_neutral_games_state_reader() -> None:
    update = (
        PROJECT_ROOT
        / "scripts"
        / "commands"
        / "update.sh"
    ).read_text(encoding="utf-8")

    start = update.index(
        "atlas_update_validate_ingress_build_permissions()"
    )
    end = update.index(
        "\natlas_update_core_prepare()",
        start,
    )
    block = update[start:end]

    assert "modules/sports/src/games_state.py" in block


def test_sports_feed_uses_neutral_games_state_reader() -> None:
    feed = (
        PROJECT_ROOT
        / "modules"
        / "sports"
        / "src"
        / "feed.py"
    ).read_text(encoding="utf-8")

    assert "from games_state import load_games" in feed
    assert "def load_games(" not in feed
