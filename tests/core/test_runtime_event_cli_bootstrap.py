from __future__ import annotations

import os
import subprocess
from pathlib import Path
from unittest.mock import patch

from atlas.events import publish_event


ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / "scripts" / "atlas"


def test_publish_event_explicitly_skips_operator_env_file() -> None:
    with patch("atlas.events.subprocess.run") as run:
        publish_event(
            "sports",
            "sports.game-finished",
            {"game_id": "game-1"},
            atlas_binary="/opt/project-atlas/scripts/atlas",
        )

    kwargs = run.call_args.kwargs
    assert kwargs["check"] is True
    assert kwargs["env"]["ATLAS_SKIP_ENV_FILE"] == "1"
    assert kwargs["env"] is not os.environ


def test_atlas_cli_runtime_mode_skips_unreadable_operator_env(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / "config" / "modules").mkdir(parents=True)
    (project / "scripts" / "lib").mkdir(parents=True)
    (project / "scripts" / "commands").mkdir(parents=True)

    # This test is a source-contract regression: runtime event publishers must
    # have an explicit opt-out before the operator-only .env is sourced.
    content = ATLAS.read_text(encoding="utf-8")
    guard = 'if [[ "${ATLAS_SKIP_ENV_FILE:-0}" != "1" && -f "$ATLAS_ENV_FILE" ]]; then'
    source = 'source "$ATLAS_ENV_FILE"'

    assert guard in content
    assert source in content
    assert content.index(guard) < content.index(source)


def test_normal_cli_bootstrap_still_sources_operator_env() -> None:
    content = ATLAS.read_text(encoding="utf-8")
    assert 'ATLAS_SKIP_ENV_FILE:-0' in content
    assert 'source "$ATLAS_ENV_FILE"' in content
