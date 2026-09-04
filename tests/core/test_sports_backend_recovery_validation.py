from __future__ import annotations

import hashlib
import sqlite3
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

HELPER = (
    ROOT
    / "scripts"
    / "lib"
    / "sports-backend-recovery.sh"
)


def _build_backend_payload(
    root: Path,
) -> None:
    dispatch = (
        root
        / "backend-recovery"
        / "dispatcharr"
    )

    teamarr = (
        root
        / "backend-recovery"
        / "teamarr"
    )

    dispatch.mkdir(
        parents=True
    )

    teamarr.mkdir(
        parents=True
    )

    dump = (
        dispatch
        / "database.dump"
    )

    dump.write_bytes(
        b"PGDMP"
        b"synthetic-test-payload"
    )

    jwt = (
        dispatch
        / "jwt"
    )

    jwt.write_text(
        "synthetic-identity\n",
        encoding="utf-8",
    )

    database = (
        teamarr
        / "teamarr.db"
    )

    connection = sqlite3.connect(
        database
    )

    try:
        connection.execute(
            """
            CREATE TABLE probe (
                id INTEGER PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            INSERT INTO probe(value)
            VALUES ('ok')
            """
        )

        connection.commit()
    finally:
        connection.close()

    backend = (
        root
        / "backend-recovery"
    )

    manifest = (
        backend
        / "MANIFEST.tsv"
    )

    manifest.write_text(
        "\n".join(
            [
                (
                    "surface\tarchive_path\tstatus"
                ),
                (
                    "dispatcharr-database\t"
                    "backend-recovery/dispatcharr/database.dump\t"
                    "captured"
                ),
                (
                    "dispatcharr-jwt\t"
                    "backend-recovery/dispatcharr/jwt\t"
                    "captured"
                ),
                (
                    "teamarr-database\t"
                    "backend-recovery/teamarr/teamarr.db\t"
                    "captured"
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    rows = []

    for relative in (
        "backend-recovery/dispatcharr/database.dump",
        "backend-recovery/dispatcharr/jwt",
        "backend-recovery/teamarr/teamarr.db",
    ):
        path = (
            root
            / relative
        )

        digest = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()

        rows.append(
            f"{digest}  {relative}"
        )

    (
        backend
        / "SHA256SUMS"
    ).write_text(
        "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


def _validate_stage(
    root: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "bash",
            "-c",
            (
                'set -euo pipefail; '
                'source "$HELPER"; '
                'atlas_sports_backend_recovery_validate_staged '
                '"$STAGE"'
            ),
        ],
        cwd=ROOT,
        env={
            "HELPER": str(HELPER),
            "STAGE": str(root),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )


def test_valid_backend_payload_passes_staged_validation(
    tmp_path: Path,
) -> None:
    _build_backend_payload(
        tmp_path
    )

    result = _validate_stage(
        tmp_path
    )

    assert (
        result.returncode == 0
    ), result.stderr


def test_backend_payload_checksum_mismatch_fails_closed(
    tmp_path: Path,
) -> None:
    _build_backend_payload(
        tmp_path
    )

    (
        tmp_path
        / "backend-recovery"
        / "dispatcharr"
        / "jwt"
    ).write_text(
        "changed\n",
        encoding="utf-8",
    )

    result = _validate_stage(
        tmp_path
    )

    assert result.returncode != 0

    assert (
        "checksum mismatch"
        in result.stderr
    )


def test_partial_backend_capture_fails_closed(
    tmp_path: Path,
) -> None:
    _build_backend_payload(
        tmp_path
    )

    manifest = (
        tmp_path
        / "backend-recovery"
        / "MANIFEST.tsv"
    )

    content = manifest.read_text(
        encoding="utf-8"
    )

    content = content.replace(
        (
            "teamarr-database\t"
            "backend-recovery/teamarr/teamarr.db\t"
            "captured"
        ),
        (
            "teamarr-database\t"
            "backend-recovery/teamarr/teamarr.db\t"
            "absent"
        ),
    )

    manifest.write_text(
        content,
        encoding="utf-8",
    )

    result = _validate_stage(
        tmp_path
    )

    assert result.returncode != 0

    assert (
        "partial"
        in result.stderr
    )
