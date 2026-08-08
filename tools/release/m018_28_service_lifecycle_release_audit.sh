#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
ARCHIVE_BASE="${2:-/mnt/storage/backups/atlas/dev-artifacts}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
AUDIT_DIR="$ROOT/.atlas-review/m018.28-$STAMP"
ARCHIVE_DIR="$ARCHIVE_BASE/$STAMP"
REPORT="$AUDIT_DIR/M018_SERVICE_LIFECYCLE_RELEASE_AUDIT.md"
BUNDLE="$ROOT/m018.28-service-lifecycle-audit-$STAMP.zip"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

record() {
  printf '%s\n' "$*" | tee -a "$AUDIT_DIR/audit.log"
}

run_logged() {
  local name="$1"
  shift
  record ""
  record "==> $name"
  "$@" >"$AUDIT_DIR/$name.stdout" 2>"$AUDIT_DIR/$name.stderr" || {
    local status=$?
    record "FAILED: $name (exit $status)"
    return "$status"
  }
  record "PASSED: $name"
}

[[ -d "$ROOT/.git" ]] || die "Not a Git repository: $ROOT"
cd "$ROOT"

BRANCH="$(git branch --show-current)"
[[ "$BRANCH" == "feature/public-ingress" ]] || \
  die "Expected feature/public-ingress; found: ${BRANCH:-detached}"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
elif [[ -x "$ROOT/.venv-api/bin/python" ]]; then
  PYTHON="$ROOT/.venv-api/bin/python"
else
  PYTHON="$(command -v python3)"
fi

mkdir -p \
  "$AUDIT_DIR/runtime/human" \
  "$AUDIT_DIR/runtime/json" \
  "$AUDIT_DIR/repository" \
  "$AUDIT_DIR/documentation" \
  "$ARCHIVE_DIR/tools/apply"

: > "$AUDIT_DIR/audit.log"

record "Project Atlas M-018.28 Service Lifecycle Release Audit"
record "Timestamp: $STAMP"
record "Branch: $BRANCH"
record "Commit: $(git rev-parse HEAD)"
record "Python: $PYTHON"

# Archive completed apply helpers, preserving the current release-audit script.
shopt -s nullglob
for path in tools/apply/m018_*.sh; do
  case "$(basename "$path")" in
    m018_28_service_lifecycle_release_audit.sh)
      continue
      ;;
  esac

  if git ls-files --error-unmatch "$path" >/dev/null 2>&1; then
    record "Tracked helper preserved: $path"
    continue
  fi

  mv -- "$path" "$ARCHIVE_DIR/tools/apply/$(basename "$path")"
  record "Archived completed helper: $path"
done
shopt -u nullglob

# Repository snapshots.
git status --short > "$AUDIT_DIR/repository/git-status-short.txt"
git diff --stat > "$AUDIT_DIR/repository/git-diff-stat.txt"
git diff --name-status > "$AUDIT_DIR/repository/git-diff-name-status.txt"
git diff > "$AUDIT_DIR/repository/git-diff.patch"
git ls-files > "$AUDIT_DIR/repository/tracked-files.txt"
find atlas/service_lifecycle -maxdepth 3 -type f -print \
  | sort > "$AUDIT_DIR/repository/service-lifecycle-tree.txt"
find tools -maxdepth 3 -type f -print \
  | sort > "$AUDIT_DIR/repository/tools-tree.txt"

run_logged git-diff-check git diff --check

run_logged python-compileall \
  "$PYTHON" -m compileall -q \
  atlas \
  tests/core \
  scripts

run_logged shell-syntax \
  bash -c '
set -Eeuo pipefail
for file in scripts/atlas scripts/commands/*.sh tools/**/*.sh; do
  [[ -f "$file" ]] || continue
  bash -n "$file"
done
'

run_logged public-api-validation \
  "$PYTHON" - <<'PY'
import atlas.service_lifecycle.service as legacy_lifecycle
import atlas.service_lifecycle.doctor as legacy_doctor
import atlas.service_lifecycle.update as legacy_updates
import atlas.service_lifecycle.maintenance as legacy_maintenance

import atlas.service_lifecycle.services.lifecycle as canonical_lifecycle
import atlas.service_lifecycle.services.doctor as canonical_doctor
import atlas.service_lifecycle.services.updates as canonical_updates
import atlas.service_lifecycle.services.maintenance as canonical_maintenance

from atlas.service_lifecycle import (
    DoctorReport,
    MaintenanceReport,
    ServiceDoctor,
    ServiceLifecycleService,
    ServiceMaintenanceHistoryService,
    ServiceUpdateService,
    UpdateReport,
)

assert legacy_lifecycle is canonical_lifecycle
assert legacy_doctor is canonical_doctor
assert legacy_updates is canonical_updates
assert legacy_maintenance is canonical_maintenance

assert ServiceLifecycleService is canonical_lifecycle.ServiceLifecycleService
assert ServiceDoctor is canonical_doctor.ServiceDoctor
assert ServiceUpdateService is canonical_updates.ServiceUpdateService
assert (
    ServiceMaintenanceHistoryService
    is canonical_maintenance.ServiceMaintenanceHistoryService
)

assert DoctorReport
assert UpdateReport
assert MaintenanceReport

print("Public API and compatibility aliases validated.")
PY

run_logged documentation-validation \
  "$PYTHON" - <<'PY'
from pathlib import Path
import re

root = Path(".")
documents = (
    Path("docs/architecture/README.md"),
    Path("docs/architecture/SERVICE_LIFECYCLE.md"),
    Path("docs/cli/SERVICE_LIFECYCLE.md"),
    Path("docs/api/SERVICE_LIFECYCLE.md"),
    Path("docs/ENGINEERING_GUIDE.md"),
    Path("docs/ENGINEERING_CHECKLIST.md"),
    Path("docs/BUILD_LOG.md"),
    Path("CHANGELOG.md"),
    Path("ROADMAP.md"),
)

for document in documents:
    if not document.is_file():
        raise SystemExit(f"Missing document: {document}")

link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
failures: list[str] = []

for document in documents:
    text = document.read_text()
    for target in link_pattern.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        local_target = target.split("#", 1)[0]
        if not local_target:
            continue
        resolved = (document.parent / local_target).resolve()
        if not resolved.exists():
            failures.append(f"{document}: broken link -> {target}")

if failures:
    raise SystemExit("\n".join(failures))

cli_doc = Path("docs/cli/SERVICE_LIFECYCLE.md").read_text()
for command in (
    "list",
    "show",
    "runtime",
    "health",
    "summary",
    "graph",
    "doctor",
    "updates",
    "history",
):
    if f"atlas service {command}" not in cli_doc:
        raise SystemExit(f"CLI documentation missing: {command}")

api_doc = Path("docs/api/SERVICE_LIFECYCLE.md").read_text()
for public_name in (
    "ServiceLifecycleService",
    "ServiceDoctor",
    "ServiceUpdateService",
    "ServiceMaintenanceHistoryService",
):
    if public_name not in api_doc:
        raise SystemExit(f"API documentation missing: {public_name}")

print("Documentation files, links, CLI commands, and public APIs validated.")
PY

run_logged full-pytest \
  "$PYTHON" -m pytest -q

# Resolve one real managed service.
./scripts/atlas service list --json \
  > "$AUDIT_DIR/runtime/json/list.json"

FIRST_SERVICE="$(
  "$PYTHON" - "$AUDIT_DIR/runtime/json/list.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())

if isinstance(payload, dict):
    services = payload.get("services", [])
elif isinstance(payload, list):
    services = payload
else:
    raise SystemExit("Unexpected service-list JSON contract")

if not services:
    raise SystemExit("No managed services found")

print(services[0]["identifier"])
PY
)" || die "Unable to resolve a managed service"

record "Runtime smoke-test service: $FIRST_SERVICE"
printf '%s\n' "$FIRST_SERVICE" > "$AUDIT_DIR/runtime/selected-service.txt"

# Human command smoke tests.
declare -a HUMAN_COMMANDS=(
  "list"
  "show $FIRST_SERVICE"
  "runtime $FIRST_SERVICE"
  "health"
  "health $FIRST_SERVICE"
  "summary"
  "graph"
  "doctor"
  "updates"
  "history"
  "history $FIRST_SERVICE"
)

for command in "${HUMAN_COMMANDS[@]}"; do
  safe_name="${command// /-}"
  ./scripts/atlas service $command \
    > "$AUDIT_DIR/runtime/human/$safe_name.txt"
  record "PASSED: atlas service $command"
done

# JSON command smoke tests.
declare -a JSON_COMMANDS=(
  "list"
  "show $FIRST_SERVICE"
  "runtime $FIRST_SERVICE"
  "health"
  "health $FIRST_SERVICE"
  "summary"
  "graph"
  "doctor"
  "updates"
  "history"
  "history $FIRST_SERVICE"
)

for command in "${JSON_COMMANDS[@]}"; do
  safe_name="${command// /-}"
  ./scripts/atlas service $command --json \
    > "$AUDIT_DIR/runtime/json/$safe_name.json"
  record "PASSED: atlas service $command --json"
done

run_logged runtime-json-contracts \
  "$PYTHON" - "$AUDIT_DIR/runtime/json" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = sorted(root.glob("*.json"))
if not files:
    raise SystemExit("No runtime JSON files were generated")

for path in files:
    payload = json.loads(path.read_text())

    if path.name == "doctor.json":
        required = {"findings", "counts", "status"}
        missing = required - payload.keys()
        if missing:
            raise SystemExit(f"{path.name} missing {sorted(missing)}")

    if path.name == "updates.json":
        required = {
            "updates",
            "counts",
            "status",
            "provider",
            "total_services",
        }
        missing = required - payload.keys()
        if missing:
            raise SystemExit(f"{path.name} missing {sorted(missing)}")
        if payload["total_services"] != len(payload["updates"]):
            raise SystemExit("updates total_services mismatch")
        if payload["counts"].get("update-available", 0) != 0:
            raise SystemExit(
                "Local-only update discovery claimed an available update"
            )

    if path.name.startswith("history"):
        required = {
            "records",
            "counts",
            "provider",
            "total_records",
            "requires_attention",
        }
        missing = required - payload.keys()
        if missing:
            raise SystemExit(f"{path.name} missing {sorted(missing)}")
        if payload["total_records"] != len(payload["records"]):
            raise SystemExit(f"{path.name} total_records mismatch")

print(f"Validated {len(files)} runtime JSON contracts.")
PY

# Capture live help and verify all commands.
./scripts/atlas service help \
  > "$AUDIT_DIR/runtime/human/service-help.txt"

for command in \
  list show runtime health summary graph doctor updates history
do
  grep -Eq "^[[:space:]]+$command[[:space:]]" \
    "$AUDIT_DIR/runtime/human/service-help.txt" || \
    die "Live help missing command: $command"
done
record "PASSED: live service help contract"

# Repository hygiene checks.
"$PYTHON" - <<'PY' > "$AUDIT_DIR/repository/hygiene.txt"
from pathlib import Path

root = Path(".")
forbidden_suffixes = (
    ".pyc",
    ".pyo",
)
forbidden_names = {
    "__pycache__",
    ".pytest_cache",
}

issues: list[str] = []

for path in root.rglob("*"):
    if ".git" in path.parts or ".venv" in path.parts:
        continue
    if path.name in forbidden_names:
        issues.append(str(path))
    if path.is_file() and path.suffix in forbidden_suffixes:
        issues.append(str(path))

if issues:
    print("Generated cache artifacts detected:")
    for issue in sorted(issues):
        print(issue)
else:
    print("No generated cache artifacts detected outside ignored environments.")
PY

# Build the permanent audit report.
FULL_TEST_RESULT="$(
  tail -n 5 "$AUDIT_DIR/full-pytest.stdout" | tr '\n' ' '
)"

cat <<DOC > "$REPORT"
# M-018 Service Lifecycle Release Audit

## Audit Identity

- Timestamp: \`$STAMP\`
- Branch: \`$BRANCH\`
- Commit: \`$(git rev-parse HEAD)\`
- Runtime service: \`$FIRST_SERVICE\`
- Python: \`$PYTHON\`

## Scope

This audit certifies the read-only Service Lifecycle subsystem implemented
through M-018.27.

Validated capabilities:

- managed-service inventory;
- service identity and runtime inspection;
- service and aggregate health;
- infrastructure summary;
- dependency graph;
- Service Doctor diagnostics;
- Update Discovery;
- Maintenance History;
- human-readable and JSON CLI surfaces;
- canonical and legacy Python imports;
- architecture, CLI, and API documentation.

## Engineering Results

- Git whitespace validation: passed.
- Python compilation: passed.
- Shell syntax validation: passed.
- Public API validation: passed.
- Compatibility aliases: passed.
- Documentation and link validation: passed.
- Full repository test suite: passed.
- Runtime human command validation: passed.
- Runtime JSON command validation: passed.
- Live help contract: passed.

Full test output tail:

\`\`\`text
$FULL_TEST_RESULT
\`\`\`

## Runtime Validation

The following commands were executed in human and JSON forms where supported:

\`\`\`text
atlas service list
atlas service show $FIRST_SERVICE
atlas service runtime $FIRST_SERVICE
atlas service health
atlas service health $FIRST_SERVICE
atlas service summary
atlas service graph
atlas service doctor
atlas service updates
atlas service history
atlas service history $FIRST_SERVICE
\`\`\`

## Public API Stability

Canonical services:

\`\`\`python
ServiceLifecycleService
ServiceDoctor
ServiceUpdateService
ServiceMaintenanceHistoryService
\`\`\`

Compatibility module paths were verified as true aliases:

\`\`\`text
atlas.service_lifecycle.service
atlas.service_lifecycle.doctor
atlas.service_lifecycle.update
atlas.service_lifecycle.maintenance
\`\`\`

## Safety Boundary

The audited v1.0 Service Lifecycle subsystem is read-only.

It does not:

- pull images;
- restart services;
- stop or start containers;
- recreate containers;
- execute maintenance;
- persist Maintenance History;
- mutate Docker.

## Administration Portal Readiness

The subsystem is ready to support the v1.0 Administration Portal through the
existing normalized services and report contracts.

The Portal should consume these services through a thin API or adapter layer and
must not call Docker directly.

## Remaining Work

- Review the complete repository diff.
- Confirm ROADMAP status and completion language.
- Archive the M-018.28 audit helper after commit.
- Commit the completed M-018 milestone.
- Push \`feature/public-ingress\`.
- Begin the v1.0 Administration Portal milestone.

## Audit Result

**PASS — M-018 Service Lifecycle is release-candidate ready, subject to final
diff review, roadmap update, commit, and push.**
DOC

# Copy key documents and source snapshots into the audit bundle.
cp -a \
  docs/architecture/SERVICE_LIFECYCLE.md \
  "$AUDIT_DIR/documentation/"
cp -a \
  docs/cli/SERVICE_LIFECYCLE.md \
  "$AUDIT_DIR/documentation/CLI_SERVICE_LIFECYCLE.md"
cp -a \
  docs/api/SERVICE_LIFECYCLE.md \
  "$AUDIT_DIR/documentation/API_SERVICE_LIFECYCLE.md"
cp -a \
  docs/ENGINEERING_GUIDE.md \
  docs/ENGINEERING_CHECKLIST.md \
  "$AUDIT_DIR/documentation/"

rm -f "$BUNDLE"
(
  cd "$ROOT"
  zip -qr "$BUNDLE" \
    ".atlas-review/$(basename "$AUDIT_DIR")"
)

record ""
record "M-018.28 release audit completed successfully."
record "Audit directory: $AUDIT_DIR"
record "Audit report:    $REPORT"
record "Review bundle:   $BUNDLE"
record ""
record "Review next:"
record "  cat $REPORT"
record "  git status --short"
record "  git diff --check"
record "  git diff --stat"
record "  git diff -- ROADMAP.md CHANGELOG.md docs/BUILD_LOG.md"
