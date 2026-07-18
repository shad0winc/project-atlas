#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
SPORTS_SRC_DIR = TEST_DIR.parent / "src"

def discover_tests() -> list[Path]:
    return sorted(
        path
        for path in TEST_DIR.glob("integration_*.py")
        if path.name != "run_tests.py"
    )

def run_test(test: Path) -> bool:
    print(f"\nRunning {test.name}")
    print("-" * 60)

    env = os.environ.copy()

    # Integration recording and scheduler tests require the
    # deterministic FFmpeg recorder rather than fake sleep mode.
    env["SPORTS_RECORDER_MODE"] = "ffmpeg"

    existing = env.get("PYTHONPATH", "")

    paths = [str(SPORTS_SRC_DIR)]

    if existing:
        paths.append(existing)

    env["PYTHONPATH"] = os.pathsep.join(paths)

    result = subprocess.run(
        [sys.executable, str(test)],
        cwd=TEST_DIR,
        env=env,
    )

    return result.returncode == 0

def main() -> int:
    print("Project Atlas")
    print("Sports Module Test Suite")
    print("=" * 60)

    tests = discover_tests()

    if not tests:
        print("No integration tests discovered.")
        return 1

    passed = 0
    failed = 0

    for test in tests:
        if run_test(test):
            print(f"PASS {test.name}")
            passed += 1
        else:
            print(f"FAIL {test.name}")
            failed += 1

    print("\nSummary")
    print("-" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    if failed:
        print("\nSports Module: FAIL")
        return 1

    print("\nSports Module: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
