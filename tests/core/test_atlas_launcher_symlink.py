"""The Atlas CLI must resolve its project root through installed symlinks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_launcher_root_resolves_through_symlink(tmp_path: Path) -> None:
    source = (PROJECT_ROOT / "scripts" / "atlas").read_text()
    # Execute the real launcher's root-discovery prelude in a disposable tree.
    prelude = source.split('if [[ "${ATLAS_SKIP_ENV_FILE:-0}"', 1)[0]
    assert "readlink -f" in prelude

    root = tmp_path / "project"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    launcher = scripts / "atlas"
    launcher.write_text(prelude + '\nprintf "%s\\n" "$PROJECT_DIR"\n')
    launcher.chmod(0o755)
    link = tmp_path / "bin" / "atlas"
    link.parent.mkdir()
    link.symlink_to(launcher)

    environment = os.environ.copy()
    environment.pop("ATLAS_PROJECT_DIR", None)
    result = subprocess.run(
        [str(link)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    assert result.stdout.strip() == str(root)

    environment["ATLAS_PROJECT_DIR"] = str(tmp_path / "override")
    result = subprocess.run(
        [str(link)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=5,
        check=True,
    )
    assert result.stdout.strip() == environment["ATLAS_PROJECT_DIR"]
