#!/usr/bin/env bash

# Project Atlas Sports backend application-consistent recovery support.
#
# These artifacts are intentionally separate from the canonical filesystem
# replacement registry. Native live restore is not enabled by this library.

atlas_sports_backend_recovery_rows() {
  printf '%s\t%s\n' \
    'dispatcharr-database' \
    'backend-recovery/dispatcharr/database.dump'

  printf '%s\t%s\n' \
    'dispatcharr-jwt' \
    'backend-recovery/dispatcharr/jwt'

  printf '%s\t%s\n' \
    'teamarr-database' \
    'backend-recovery/teamarr/teamarr.db'
}

atlas_sports_backend_recovery_validate_staged() {
  local root="$1"

  python3 - "$root" <<'PY'
import hashlib
import sqlite3
import sys
from pathlib import Path

root = Path(sys.argv[1])
backend = root / "backend-recovery"

manifest = backend / "MANIFEST.tsv"
checksums = backend / "SHA256SUMS"

expected = [
    (
        "dispatcharr-database",
        "backend-recovery/dispatcharr/database.dump",
    ),
    (
        "dispatcharr-jwt",
        "backend-recovery/dispatcharr/jwt",
    ),
    (
        "teamarr-database",
        "backend-recovery/teamarr/teamarr.db",
    ),
]

expected_paths = {path for _, path in expected}

if not backend.is_dir() or backend.is_symlink():
    raise SystemExit(
        "ERROR: Sports backend recovery root is invalid"
    )

for path in backend.rglob("*"):
    if path.is_symlink():
        raise SystemExit(
            "ERROR: Sports backend recovery contains a symbolic link"
        )

if not manifest.is_file() or manifest.is_symlink():
    raise SystemExit(
        "ERROR: Sports backend recovery manifest is invalid"
    )

if not checksums.is_file() or checksums.is_symlink():
    raise SystemExit(
        "ERROR: Sports backend recovery checksums are invalid"
    )

lines = [
    line
    for line in manifest.read_text(
        encoding="utf-8"
    ).splitlines()
    if line
]

if (
    len(lines) != 4
    or lines[0] != "surface\tarchive_path\tstatus"
):
    raise SystemExit(
        "ERROR: Sports backend recovery manifest is invalid"
    )

statuses = []

for raw, expected_row in zip(
    lines[1:],
    expected,
    strict=True,
):
    fields = raw.split("\t")

    if len(fields) != 3:
        raise SystemExit(
            "ERROR: Sports backend recovery row is malformed"
        )

    surface, archive_path, status = fields

    if (
        (surface, archive_path) != expected_row
        or status not in {"captured", "absent"}
    ):
        raise SystemExit(
            "ERROR: Sports backend recovery contract mismatch"
        )

    statuses.append(status)

if len(set(statuses)) != 1:
    raise SystemExit(
        "ERROR: Sports backend recovery is partial"
    )

captured = statuses[0] == "captured"

if not captured:
    if checksums.read_text(
        encoding="utf-8"
    ).strip():
        raise SystemExit(
            "ERROR: absent backend state has checksums"
        )

    for relative in expected_paths:
        if (root / relative).exists():
            raise SystemExit(
                "ERROR: absent backend state has artifacts"
            )

    raise SystemExit(0)

checksum_rows = {}

for raw in checksums.read_text(
    encoding="utf-8"
).splitlines():
    if not raw:
        continue

    if "  " not in raw:
        raise SystemExit(
            "ERROR: backend checksum row is malformed"
        )

    digest, relative = raw.split("  ", 1)

    if (
        len(digest) != 64
        or relative not in expected_paths
        or relative in checksum_rows
    ):
        raise SystemExit(
            "ERROR: backend checksum contract is invalid"
        )

    checksum_rows[relative] = digest

if set(checksum_rows) != expected_paths:
    raise SystemExit(
        "ERROR: backend checksum coverage is incomplete"
    )

for relative, expected_digest in checksum_rows.items():
    path = root / relative

    if not path.is_file() or path.is_symlink():
        raise SystemExit(
            f"ERROR: backend artifact is invalid: {relative}"
        )

    actual = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()

    if actual != expected_digest:
        raise SystemExit(
            f"ERROR: backend checksum mismatch: {relative}"
        )

dispatch_dump = (
    root
    / "backend-recovery"
    / "dispatcharr"
    / "database.dump"
)

if dispatch_dump.read_bytes()[:5] != b"PGDMP":
    raise SystemExit(
        "ERROR: Dispatcharr recovery dump format is invalid"
    )

dispatch_jwt = (
    root
    / "backend-recovery"
    / "dispatcharr"
    / "jwt"
)

if dispatch_jwt.stat().st_size == 0:
    raise SystemExit(
        "ERROR: Dispatcharr recovery identity is empty"
    )

teamarr_db = (
    root
    / "backend-recovery"
    / "teamarr"
    / "teamarr.db"
)

connection = sqlite3.connect(
    str(teamarr_db)
)

try:
    result = connection.execute(
        "PRAGMA integrity_check"
    ).fetchone()
finally:
    connection.close()

if not result or result[0] != "ok":
    raise SystemExit(
        "ERROR: Teamarr recovery database failed integrity validation"
    )
PY
}


atlas_sports_backend_recovery_validate_archive() {
  local archive="$1"

  python3 - "$archive" <<'PY_ARCHIVE'
import hashlib
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import PurePosixPath

archive_path = sys.argv[1]

expected = [
    (
        "dispatcharr-database",
        "backend-recovery/dispatcharr/database.dump",
    ),
    (
        "dispatcharr-jwt",
        "backend-recovery/dispatcharr/jwt",
    ),
    (
        "teamarr-database",
        "backend-recovery/teamarr/teamarr.db",
    ),
]

artifact_paths = {
    path
    for _, path in expected
}

manifest_name = (
    "backend-recovery/MANIFEST.tsv"
)

checksums_name = (
    "backend-recovery/SHA256SUMS"
)

allowed_directories = {
    "backend-recovery",
    "backend-recovery/dispatcharr",
    "backend-recovery/teamarr",
}

allowed_metadata = {
    manifest_name,
    checksums_name,
}


def normalized_name(
    raw: str,
) -> str:
    return raw.rstrip("/")


def validate_relative_name(
    name: str,
) -> None:
    path = PurePosixPath(name)

    if (
        not name
        or name.startswith("/")
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
    ):
        raise SystemExit(
            "ERROR: unsafe Sports backend recovery member path"
        )


try:
    archive = tarfile.open(
        archive_path,
        mode="r:gz",
    )
except (OSError, tarfile.TarError) as exc:
    raise SystemExit(
        "ERROR: unable to inspect Sports backend "
        f"recovery archive: {exc}"
    )


with archive:
    members = {}

    for member in archive.getmembers():
        name = normalized_name(
            member.name
        )

        if not (
            name == "backend-recovery"
            or name.startswith(
                "backend-recovery/"
            )
        ):
            continue

        validate_relative_name(
            name
        )

        if name in members:
            raise SystemExit(
                "ERROR: duplicate Sports backend "
                f"recovery member: {name}"
            )

        if (
            member.issym()
            or member.islnk()
        ):
            raise SystemExit(
                "ERROR: Sports backend recovery "
                f"contains link member: {name}"
            )

        if name in allowed_directories:
            if not member.isdir():
                raise SystemExit(
                    "ERROR: Sports backend recovery "
                    f"directory type is invalid: {name}"
                )

            members[name] = member
            continue

        if (
            name in allowed_metadata
            or name in artifact_paths
        ):
            if not member.isfile():
                raise SystemExit(
                    "ERROR: Sports backend recovery "
                    f"file type is invalid: {name}"
                )

            members[name] = member
            continue

        raise SystemExit(
            "ERROR: undeclared Sports backend "
            f"recovery member: {name}"
        )

    manifest_member = members.get(
        manifest_name
    )

    checksums_member = members.get(
        checksums_name
    )

    if (
        manifest_member is None
        or not manifest_member.isfile()
    ):
        raise SystemExit(
            "ERROR: Sports backend recovery "
            "manifest is unavailable"
        )

    if (
        checksums_member is None
        or not checksums_member.isfile()
    ):
        raise SystemExit(
            "ERROR: Sports backend recovery "
            "checksums are unavailable"
        )

    manifest_file = archive.extractfile(
        manifest_member
    )

    checksums_file = archive.extractfile(
        checksums_member
    )

    if (
        manifest_file is None
        or checksums_file is None
    ):
        raise SystemExit(
            "ERROR: Sports backend recovery "
            "metadata is unreadable"
        )

    manifest = manifest_file.read().decode(
        "utf-8",
        errors="strict",
    )

    checksum_text = (
        checksums_file
        .read()
        .decode(
            "utf-8",
            errors="strict",
        )
    )

    lines = [
        line
        for line in manifest.splitlines()
        if line
    ]

    if (
        len(lines) != 4
        or lines[0]
        != "surface\tarchive_path\tstatus"
    ):
        raise SystemExit(
            "ERROR: Sports backend recovery "
            "manifest is invalid"
        )

    statuses = []

    for raw, expected_row in zip(
        lines[1:],
        expected,
        strict=True,
    ):
        fields = raw.split("\t")

        if len(fields) != 3:
            raise SystemExit(
                "ERROR: Sports backend recovery "
                "manifest row is malformed"
            )

        (
            surface,
            member_path,
            status,
        ) = fields

        if (
            (surface, member_path)
            != expected_row
        ):
            raise SystemExit(
                "ERROR: Sports backend recovery "
                "manifest contract mismatch"
            )

        if status not in {
            "captured",
            "absent",
        }:
            raise SystemExit(
                "ERROR: Sports backend recovery "
                "status is invalid"
            )

        statuses.append(
            status
        )

    if len(set(statuses)) != 1:
        raise SystemExit(
            "ERROR: Sports backend recovery "
            "capture is partial"
        )

    captured = (
        statuses[0]
        == "captured"
    )

    if not captured:
        if checksum_text.strip():
            raise SystemExit(
                "ERROR: absent Sports backend "
                "recovery contains checksums"
            )

        for member_path in artifact_paths:
            if member_path in members:
                raise SystemExit(
                    "ERROR: absent Sports backend "
                    "recovery contains artifacts"
                )

        raise SystemExit(0)

    for member_path in artifact_paths:
        if member_path not in members:
            raise SystemExit(
                "ERROR: Sports backend recovery "
                f"artifact is missing: {member_path}"
            )

    checksum_rows = {}

    for raw in checksum_text.splitlines():
        if not raw:
            continue

        if "  " not in raw:
            raise SystemExit(
                "ERROR: Sports backend recovery "
                "checksum row is malformed"
            )

        digest, member_path = (
            raw.split(
                "  ",
                1,
            )
        )

        if (
            len(digest) != 64
            or any(
                ch not in
                "0123456789abcdef"
                for ch in digest
            )
            or member_path
            not in artifact_paths
            or member_path
            in checksum_rows
        ):
            raise SystemExit(
                "ERROR: Sports backend recovery "
                "checksum contract is invalid"
            )

        checksum_rows[
            member_path
        ] = digest

    if (
        set(checksum_rows)
        != artifact_paths
    ):
        raise SystemExit(
            "ERROR: Sports backend recovery "
            "checksum coverage is incomplete"
        )

    payloads = {}

    for member_path in sorted(
        artifact_paths
    ):
        extracted = archive.extractfile(
            members[member_path]
        )

        if extracted is None:
            raise SystemExit(
                "ERROR: Sports backend recovery "
                f"artifact is unreadable: {member_path}"
            )

        payload = extracted.read()

        actual = hashlib.sha256(
            payload
        ).hexdigest()

        if (
            actual
            != checksum_rows[
                member_path
            ]
        ):
            raise SystemExit(
                "ERROR: Sports backend recovery "
                f"checksum mismatch: {member_path}"
            )

        payloads[
            member_path
        ] = payload

    dispatch_dump = payloads[
        "backend-recovery/"
        "dispatcharr/"
        "database.dump"
    ]

    if not dispatch_dump.startswith(
        b"PGDMP"
    ):
        raise SystemExit(
            "ERROR: Dispatcharr recovery dump "
            "format is invalid"
        )

    dispatch_identity = payloads[
        "backend-recovery/"
        "dispatcharr/"
        "jwt"
    ]

    if not dispatch_identity:
        raise SystemExit(
            "ERROR: Dispatcharr recovery "
            "identity is empty"
        )

    teamarr_payload = payloads[
        "backend-recovery/"
        "teamarr/"
        "teamarr.db"
    ]

    with tempfile.NamedTemporaryFile(
        suffix=".db"
    ) as temporary:
        temporary.write(
            teamarr_payload
        )

        temporary.flush()

        connection = sqlite3.connect(
            temporary.name
        )

        try:
            result = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()
        finally:
            connection.close()

        if (
            not result
            or result[0] != "ok"
        ):
            raise SystemExit(
                "ERROR: Teamarr recovery "
                "database failed integrity validation"
            )
PY_ARCHIVE
}


atlas_sports_backend_recovery_capture() {
  local snapshot_root="$1"

  : "${ATLAS_CONFIG_ROOT:?ATLAS_CONFIG_ROOT is required}"

  local dispatch_root="$ATLAS_CONFIG_ROOT/dispatcharr"
  local teamarr_root="$ATLAS_CONFIG_ROOT/teamarr"

  local target_root="$snapshot_root/backend-recovery"
  local dispatch_target="$target_root/dispatcharr"
  local teamarr_target="$target_root/teamarr"

  local manifest="$target_root/MANIFEST.tsv"
  local checksums="$target_root/SHA256SUMS"

  local dispatch_tmp
  local teamarr_tmp

  [[ "$snapshot_root" == /* &&
     -d "$snapshot_root" &&
     ! -L "$snapshot_root" ]] || {
    echo \
      'ERROR: Sports backend recovery snapshot root is invalid.' \
      >&2
    return 1
  }

  mkdir -p "$target_root"
  chmod 0700 "$target_root"

  printf '%s\t%s\t%s\n' \
    'surface' \
    'archive_path' \
    'status' \
    > "$manifest"

  if [[ ! -e "$dispatch_root" &&
        ! -e "$teamarr_root" ]]
  then
    while IFS=$'\t' read -r surface archive_path; do
      printf '%s\t%s\t%s\n' \
        "$surface" \
        "$archive_path" \
        'absent' \
        >> "$manifest"
    done < <(
      atlas_sports_backend_recovery_rows
    )

    : > "$checksums"

    chmod 0600 \
      "$manifest" \
      "$checksums"

    return 0
  fi

  [[ -d "$dispatch_root" &&
     ! -L "$dispatch_root" &&
     -d "$teamarr_root" &&
     ! -L "$teamarr_root" ]] || {
    echo \
      'ERROR: Sports backend state is only partially present.' \
      >&2
    return 1
  }

  [[ -f "$dispatch_root/jwt" &&
     ! -L "$dispatch_root/jwt" ]] || {
    echo \
      'ERROR: Dispatcharr persistent identity is unavailable.' \
      >&2
    return 1
  }

  for container in \
    atlas-dispatcharr \
    atlas-teamarr
  do
    test "$(
      docker inspect "$container" \
        --format '{{.State.Status}}' \
        2>/dev/null
    )" = 'running' || {
      printf \
        'ERROR: Sports backend recovery container is unavailable: %s\n' \
        "$container" \
        >&2
      return 1
    }
  done

  mkdir -p \
    "$dispatch_target" \
    "$teamarr_target"

  chmod 0700 \
    "$dispatch_target" \
    "$teamarr_target"

  dispatch_tmp="/tmp/atlas-recovery-${BASHPID}-${RANDOM}.dump"

  if ! docker exec \
    atlas-dispatcharr \
    sh -lc \
    "cd /app &&
     test -f manage.py &&
     python3 manage.py shell -c \
     'from pathlib import Path; from apps.backups.services import _dump_postgresql; _dump_postgresql(Path(\"$dispatch_tmp\"))'" \
    >/dev/null 2>&1
  then
    docker exec atlas-dispatcharr \
      rm -f -- "$dispatch_tmp" \
      >/dev/null 2>&1 || true

    echo \
      'ERROR: Dispatcharr PostgreSQL recovery dump failed.' \
      >&2

    return 1
  fi

  if ! docker cp \
    "atlas-dispatcharr:$dispatch_tmp" \
    "$dispatch_target/database.dump" \
    >/dev/null 2>&1
  then
    docker exec atlas-dispatcharr \
      rm -f -- "$dispatch_tmp" \
      >/dev/null 2>&1 || true

    echo \
      'ERROR: unable to collect Dispatcharr recovery dump.' \
      >&2

    return 1
  fi

  docker exec atlas-dispatcharr \
    rm -f -- "$dispatch_tmp" \
    >/dev/null 2>&1 || true

  teamarr_tmp="/tmp/atlas-recovery-${BASHPID}-${RANDOM}.db"

  if ! docker exec -i \
    atlas-teamarr \
    python - "$teamarr_tmp" \
    >/dev/null 2>&1 <<'PY_TEAMARR'
import sqlite3
import sys
from pathlib import Path

source = Path("/app/data/teamarr.db")
target = Path(sys.argv[1])

if not source.is_file():
    raise SystemExit(1)

src = sqlite3.connect(str(source))
dst = sqlite3.connect(str(target))

try:
    src.backup(dst)

    result = dst.execute(
        "PRAGMA quick_check"
    ).fetchone()

    if not result or result[0] != "ok":
        raise SystemExit(1)
finally:
    dst.close()
    src.close()
PY_TEAMARR
  then
    docker exec atlas-teamarr \
      rm -f -- "$teamarr_tmp" \
      >/dev/null 2>&1 || true

    echo \
      'ERROR: Teamarr SQLite recovery backup failed.' \
      >&2

    return 1
  fi

  if ! docker cp \
    "atlas-teamarr:$teamarr_tmp" \
    "$teamarr_target/teamarr.db" \
    >/dev/null 2>&1
  then
    docker exec atlas-teamarr \
      rm -f -- "$teamarr_tmp" \
      >/dev/null 2>&1 || true

    echo \
      'ERROR: unable to collect Teamarr recovery database.' \
      >&2

    return 1
  fi

  docker exec atlas-teamarr \
    rm -f -- "$teamarr_tmp" \
    >/dev/null 2>&1 || true

  install \
    -m 0600 \
    -- \
    "$dispatch_root/jwt" \
    "$dispatch_target/jwt"

  chmod 0600 \
    "$dispatch_target/database.dump" \
    "$teamarr_target/teamarr.db"

  while IFS=$'\t' read -r surface archive_path; do
    printf '%s\t%s\t%s\n' \
      "$surface" \
      "$archive_path" \
      'captured' \
      >> "$manifest"
  done < <(
    atlas_sports_backend_recovery_rows
  )

  (
    cd "$snapshot_root"

    sha256sum -- \
      backend-recovery/dispatcharr/database.dump \
      backend-recovery/dispatcharr/jwt \
      backend-recovery/teamarr/teamarr.db
  ) > "$checksums"

  chmod 0600 \
    "$manifest" \
    "$checksums"

  atlas_sports_backend_recovery_validate_staged \
    "$snapshot_root"
}
