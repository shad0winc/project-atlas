"""Security contract for the API-readable ARI runtime snapshot."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGRESS = PROJECT_ROOT / "stack" / "ingress.yml"
ARI_SCRIPT = PROJECT_ROOT / "scripts" / "atlas-ari.sh"

RUNTIME_DIR = "/mnt/storage/configs/atlas/runtime/ari"
RUNTIME_FILE = f"{RUNTIME_DIR}/latest.json"
CANONICAL_DIR = "/mnt/storage/configs/atlas/ari"


def _api_stanza() -> str:
    lines = INGRESS.read_text().splitlines()

    start = lines.index("  api:")
    end = len(lines)

    for index in range(start + 1, len(lines)):
        line = lines[index]
        if (
            line.startswith("  ")
            and not line.startswith("    ")
            and line.endswith(":")
        ):
            end = index
            break

    return "\n".join(lines[start:end])


def test_api_mounts_only_runtime_ari_read_only() -> None:
    api = _api_stanza()

    assert f"{RUNTIME_DIR}:{RUNTIME_DIR}:ro" in api
    assert f"{CANONICAL_DIR}:{CANONICAL_DIR}" not in api
    assert "/mnt/storage:/mnt/storage" not in api


def test_api_uses_runtime_ari_snapshot() -> None:
    api = _api_stanza()

    assert f'ATLAS_ARI_LATEST_FILE: "{RUNTIME_FILE}"' in api
    assert f'ATLAS_ARI_LATEST_PATH: "{RUNTIME_FILE}"' in api


def test_runtime_projection_has_bounded_permissions() -> None:
    script = ARI_SCRIPT.read_text()

    assert (
        'install -d -o 0 -g 20000 -m 0750 "$directory"'
        in script
    )
    assert 'chown 0:20000 "$temporary"' in script
    assert 'chmod 0640 "$temporary"' in script
    assert 'mv -f -- "$temporary" "$destination"' in script

    assert "chmod -R" not in script
    assert "chown -R" not in script


def test_collection_publishes_after_canonical_latest() -> None:
    script = ARI_SCRIPT.read_text()

    canonical = '  cp "$snapshot_file" "$LATEST_FILE"'
    runtime = '  publish_api_runtime_snapshot "$LATEST_FILE"'

    assert script.count(runtime) == 1
    assert script.index(canonical) < script.index(runtime)


def test_canonical_ari_path_is_not_redefined() -> None:
    script = ARI_SCRIPT.read_text()

    assert 'ARI_DATA_DIR="$ATLAS_ARI_DIR"' in script
    assert 'LATEST_FILE="$ATLAS_ARI_LATEST_FILE"' in script
    assert (
        'ARI_API_RUNTIME_DIR="${ATLAS_ARI_API_RUNTIME_DIR:-'
        f'{RUNTIME_DIR}}}"'
    ) in script


def _publication_function() -> str:
    """Return the actual shell publication helper from atlas-ari.sh."""

    script = ARI_SCRIPT.read_text()

    start_marker = "publish_api_runtime_snapshot() {\n"
    end_marker = (
        "\n###############################################################################\n"
        "# Jellyfin Helpers\n"
    )

    start = script.index(start_marker)
    end = script.index(end_marker, start)

    return script[start:end]


def _run_publication(
    tmp_path: Path,
    *,
    source_contents: str = '{"schema_version":1}\n',
    fail_copy: bool = False,
):
    """Run the real helper with CI-safe ownership command shims."""

    import os
    import subprocess

    source = tmp_path / "canonical-latest.json"
    source.write_text(source_contents)

    runtime = tmp_path / "runtime" / "ari"
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir(exist_ok=True)

    install = fake_bin / "install"
    install.write_text(
        "#!/bin/sh\n"
        'directory=""\n'
        'for argument in "$@"; do directory="$argument"; done\n'
        'exec /usr/bin/install -d -m 0750 "$directory"\n'
    )
    install.chmod(0o755)

    chown = fake_bin / "chown"
    chown.write_text("#!/bin/sh\nexit 0\n")
    chown.chmod(0o755)

    if fail_copy:
        cp = fake_bin / "cp"
        cp.write_text("#!/bin/sh\nexit 41\n")
        cp.chmod(0o755)

    command = (
        "set -euo pipefail\n"
        f"{_publication_function()}\n"
        f'ARI_API_RUNTIME_DIR="{runtime}"\n'
        'ARI_API_RUNTIME_FILE="$ARI_API_RUNTIME_DIR/latest.json"\n'
        f'publish_api_runtime_snapshot "{source}"\n'
    )

    environment = os.environ.copy()
    environment["PATH"] = f"{fake_bin}:{environment['PATH']}"

    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
        env=environment,
        check=False,
    )

    return result, runtime


def test_runtime_publication_creates_complete_snapshot(
    tmp_path: Path,
) -> None:
    import stat

    result, runtime = _run_publication(
        tmp_path,
        source_contents='{"version":1}\n',
    )

    assert result.returncode == 0, result.stderr

    destination = runtime / "latest.json"

    assert destination.read_text() == '{"version":1}\n'
    assert stat.S_IMODE(runtime.stat().st_mode) == 0o750
    assert stat.S_IMODE(destination.stat().st_mode) == 0o640
    assert list(runtime.glob(".latest.json.*")) == []


def test_runtime_publication_atomically_replaces_existing_snapshot(
    tmp_path: Path,
) -> None:
    first, runtime = _run_publication(
        tmp_path,
        source_contents='{"version":1}\n',
    )

    assert first.returncode == 0, first.stderr

    destination = runtime / "latest.json"
    assert destination.read_text() == '{"version":1}\n'

    second, _ = _run_publication(
        tmp_path,
        source_contents='{"version":2}\n',
    )

    assert second.returncode == 0, second.stderr
    assert destination.read_text() == '{"version":2}\n'
    assert list(runtime.glob(".latest.json.*")) == []


def test_runtime_publication_cleans_temporary_on_copy_failure(
    tmp_path: Path,
) -> None:
    result, runtime = _run_publication(
        tmp_path,
        fail_copy=True,
    )

    assert result.returncode != 0
    assert "Unable to copy ARI API runtime snapshot" in result.stderr
    assert not (runtime / "latest.json").exists()
    assert list(runtime.glob(".latest.json.*")) == []
