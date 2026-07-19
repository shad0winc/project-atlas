#!/usr/bin/env python3
"""Atlas scheduler callback for Sports maintenance.

The scheduler invokes this file, which delegates execution through the
generic Atlas Module Command Interface rather than calling Sports
implementation code directly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def project_directory() -> Path:
    """Return the Project Atlas repository root."""
    return Path(__file__).resolve().parents[3]


def main() -> int:
    atlas_cli = project_directory() / "scripts" / "atlas"

    if not atlas_cli.is_file():
        print(
            f"Sports maintenance callback error: "
            f"Atlas CLI not found: {atlas_cli}",
            file=sys.stderr,
        )
        return 1

    completed = subprocess.run(
        [
            str(atlas_cli),
            "module",
            "exec",
            "sports",
            "maintenance",
        ],
        cwd=project_directory(),
        check=False,
    )

    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
