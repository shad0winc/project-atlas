from __future__ import annotations

import os
from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[2]
HELPER = (
    PROJECT_ROOT
    / "scripts"
    / "lib"
    / "password-recovery-runtime.sh"
)


def test_runtime_provision_normalizes_and_verifies_exact_file_mode(
    tmp_path: Path,
) -> None:
    identity = tmp_path / "identity"

    environment = os.environ.copy()
    environment.update(
        {
            "ATLAS_IDENTITY_DIR": str(identity),
            "ATLAS_PASSWORD_RECOVERY_RUNTIME_UID": str(os.getuid()),
            "ATLAS_PASSWORD_RECOVERY_RUNTIME_GID": str(os.getgid()),
            "ATLAS_PASSWORD_RECOVERY_RUNTIME_FILE_GID": str(os.getgid()),
            "ATLAS_TEST_PASSWORD_RECOVERY_HELPER": str(HELPER),
        }
    )

    result = subprocess.run(
        [
            "bash",
            "-c",
            r'''
set -euo pipefail

source "$ATLAS_TEST_PASSWORD_RECOVERY_HELPER"

atlas_password_recovery_runtime_provision

recovery="$(atlas_password_recovery_runtime_dir)"
registry="$(atlas_password_recovery_runtime_registry_file)"
active="$recovery/active/test.json"

printf '{}\n' > "$registry"
printf '{}\n' > "$active"

chmod 0644 "$registry" "$active"

if atlas_password_recovery_runtime_verify >/dev/null 2>&1; then
  echo 'runtime verifier incorrectly accepted mode 0644' >&2
  exit 41
fi

atlas_password_recovery_runtime_provision
atlas_password_recovery_runtime_verify

test "$(stat -c '%a' "$registry")" = '640'
test "$(stat -c '%a' "$active")" = '640'
''',
        ],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
