"""ARI health counts and history selection use complete, valid snapshots."""

from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SOURCE = (Path(__file__).resolve().parents[2] / "scripts" / "atlas-ari.sh").read_text()


def function(name: str) -> str:
    start = SOURCE.index(f"{name}() {{\n")
    end = SOURCE.index("\n}\n", start) + len("\n}\n")
    return SOURCE[start:end]


def run_bash(script: str, *, latest: Path, history: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(LATEST_FILE=str(latest), ARI_SNAPSHOT_DIR=str(history))
    return subprocess.run(
        ["bash", "-c", "set -euo pipefail\n" + script],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def report(*, movies: int, anime_movies: int, tv: int, anime_tv: int,
           jellyfin_movies: int, jellyfin_series: int, timestamp: str) -> dict:
    return {
        "timestamp": timestamp,
        "libraries": {
            "movies": {"count": movies},
            "anime_movies": {"count": anime_movies},
            "tv": {"count": tv},
            "anime_tv": {"count": anime_tv},
        },
        "jellyfin": {"counts": {
            "movies": jellyfin_movies, "series": jellyfin_series,
        }},
        "storage": {"used_bytes": 10},
    }


class ARIHealthHistoryTests(unittest.TestCase):
    def test_global_jellyfin_counts_include_anime_libraries(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            latest = root / "latest.json"
            latest.write_text(json.dumps(report(
                movies=1, anime_movies=1, tv=1, anime_tv=1,
                jellyfin_movies=2, jellyfin_series=2,
                timestamp="2026-09-28T22:12:40Z",
            )))
            script = (
                function("health_check_library_synchronization")
                + function("print_library_synchronization")
                + "health_check_library_synchronization\n"
                + "print_library_synchronization\n"
            )
            output = run_bash(script, latest=latest, history=root).stdout
            self.assertIn("Movies + Anime Movies synchronized", output)
            self.assertIn("TV + Anime TV synchronized", output)

    def test_real_total_mismatch_still_fails(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            latest = root / "latest.json"
            latest.write_text(json.dumps(report(
                movies=1, anime_movies=0, tv=1, anime_tv=1,
                jellyfin_movies=1, jellyfin_series=3,
                timestamp="2026-09-28T22:12:40Z",
            )))
            script = (
                function("health_check_library_synchronization")
                + "if health_check_library_synchronization; then exit 10; fi\n"
            )
            run_bash(script, latest=latest, history=root)

    def test_invalid_recent_history_is_skipped_without_deleting_it(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            history = root / "snapshots"
            history.mkdir()
            older = history / "2026-09-08.json"
            older.write_text(json.dumps(report(
                movies=1, anime_movies=0, tv=1, anime_tv=0,
                jellyfin_movies=1, jellyfin_series=1,
                timestamp="2026-09-08T12:00:00Z",
            )))
            invalid = history / "2026-09-13.json"
            invalid.write_text('{"libraries": ,}')
            newest = history / "2026-09-28.json"
            newest.write_text(json.dumps(report(
                movies=1, anime_movies=0, tv=1, anime_tv=1,
                jellyfin_movies=1, jellyfin_series=2,
                timestamp="2026-09-28T22:12:40Z",
            )))
            script = (
                function("get_previous_snapshot")
                + function("get_recent_snapshots")
                + function("get_snapshot_count")
                + "printf 'previous=%s\\n' \"$(get_previous_snapshot)\"\n"
                + "printf 'count=%s\\n' \"$(get_snapshot_count 5)\"\n"
                + "get_recent_snapshots 2\n"
            )
            output = run_bash(script, latest=newest, history=history).stdout
            self.assertIn(f"previous={older}", output)
            self.assertIn("count=2", output)
            self.assertNotIn(str(invalid), output)
            self.assertEqual(invalid.read_text(), '{"libraries": ,}')

    def test_single_valid_history_has_no_previous_snapshot(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            newest = root / "2026-09-28.json"
            newest.write_text('{"timestamp":"2026-09-28T22:12:40Z"}')
            (root / "2026-09-13.json").write_text('{"timestamp": ,}')
            script = (
                function("get_previous_snapshot")
                + function("get_recent_snapshots")
                + "test -z \"$(get_previous_snapshot)\"\n"
            )
            run_bash(script, latest=newest, history=root)


if __name__ == "__main__":
    unittest.main()
