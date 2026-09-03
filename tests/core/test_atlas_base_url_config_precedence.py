from __future__ import annotations

import os
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ATLAS_CONFIG = PROJECT_ROOT / "config" / "atlas.conf"


def _source_config(
    *,
    base_url: str | None,
) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()

    if base_url is None:
        environment.pop("ATLAS_BASE_URL", None)
    else:
        environment["ATLAS_BASE_URL"] = base_url

    environment["ATLAS_TEST_CONFIG"] = str(ATLAS_CONFIG)

    return subprocess.run(
        [
            "bash",
            "-c",
            r'''
set -euo pipefail
source "$ATLAS_TEST_CONFIG"
printf '%s\n' "$ATLAS_BASE_URL"
''',
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_operator_base_url_takes_precedence_over_tracked_default() -> None:
    expected = "https://atlas.shadowinc.co"

    result = _source_config(base_url=expected)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected


def test_tracked_base_url_default_remains_available() -> None:
    result = _source_config(base_url=None)

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "http://atlas.local"
