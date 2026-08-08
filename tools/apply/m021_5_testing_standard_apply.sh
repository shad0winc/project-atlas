#!/usr/bin/env bash
#
# ==============================================================================
# Project Atlas
# Sprint: M-021.5
# Artifact: Testing Standard
#
# Purpose:
#   Install the canonical Testing Standard and update governance documentation.
#
# Runtime Changes:
#   None
#
# Repository Changes:
#   Documentation only.
#
# Safe to Re-run:
#   No. Existing canonical artifact causes a guarded stop.
# ==============================================================================

set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.5-$STAMP"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -d "$ROOT/.git" ]] || die "Not a Git repository: $ROOT"
cd "$ROOT"

for path in \
  docs/governance/README.md \
  docs/ENGINEERING_GUIDE.md \
  docs/ENGINEERING_CHECKLIST.md \
  docs/BUILD_LOG.md \
  CHANGELOG.md \
  ROADMAP.md
do
  [[ -f "$path" ]] || die "Required file missing: $path"
done

[[ ! -e docs/governance/TESTING_STANDARD.md ]] || \
  die "Refusing to overwrite existing Testing Standard"

mkdir -p "$BACKUP_DIR"
for path in \
  docs/governance/README.md \
  docs/ENGINEERING_GUIDE.md \
  docs/ENGINEERING_CHECKLIST.md \
  docs/BUILD_LOG.md \
  CHANGELOG.md \
  ROADMAP.md
do
  mkdir -p "$BACKUP_DIR/$(dirname "$path")"
  cp -a "$path" "$BACKUP_DIR/$path"
done

cat <<'ATLAS_M021_5_TESTING_STANDARD_EOF' > docs/governance/TESTING_STANDARD.md
# Atlas Testing Standard

## Purpose

This document defines the canonical testing standard for Project Atlas.

Testing exists to establish confidence in behavior, compatibility, safety, and
release readiness. Tests are part of the implementation, not an optional step
performed after development.

## Testing Philosophy

Atlas tests behavior and public contracts rather than incidental implementation
details.

Tests should be deterministic, isolated, repeatable, understandable,
maintainable, proportionate to risk, and grounded in supported behavior.

A passing automated suite is necessary but not sufficient. Runtime validation,
documentation review, and repository review remain separate engineering gates.

## Testing Layers

Atlas uses complementary validation layers:

```text
Unit Tests
↓
Contract Tests
↓
Integration Tests
↓
Regression Tests
↓
Runtime Validation
↓
Release Audit
```

Each layer answers a different question. No layer replaces the others.

## Unit Tests

Unit tests validate one focused behavior in isolation.

They should:

- avoid external network or infrastructure dependencies;
- use deterministic fixtures;
- make explicit assertions;
- cover valid and invalid cases;
- remain readable without understanding unrelated modules;
- fail for one understandable reason.

## Model Tests

Every public model should have dedicated tests covering applicable behavior:

- input normalization;
- valid construction;
- invalid identity;
- invalid child contracts;
- timestamp normalization;
- invalid state combinations;
- immutability;
- deterministic `to_dict()` serialization;
- public exports.

Model tests should verify canonical values, not only successful construction.

## Service Tests

Service tests should verify:

- dependency validation;
- identity normalization;
- provider invocation;
- provider return-contract validation;
- cross-object identity enforcement;
- preservation of known Atlas errors;
- translation of unexpected provider failures;
- deterministic aggregation;
- independence from presentation layers.

Use provider test doubles that expose calls and configurable results clearly.

## Provider Tests

Provider tests should verify:

- infrastructure data translation;
- normalized domain results;
- conservative classification when information is incomplete;
- external-command handling;
- malformed external data;
- safety boundaries;
- provider-specific error behavior.

Tests must not claim registry, network, or infrastructure facts that fixtures do
not establish.

## CLI Tests

CLI tests should cover:

- command parsing;
- human-readable output;
- canonical JSON output;
- standard output and standard error separation;
- exit codes;
- normalized error rendering;
- help registration;
- legacy command compatibility where supported.

JSON assertions should compare parsed structures or canonical `to_dict()`
results rather than whitespace formatting.

## Contract Tests

Public contracts require explicit tests.

Contract testing includes:

- package exports;
- model serialization;
- report aggregation;
- provider interfaces;
- service return types;
- CLI JSON schemas;
- compatibility aliases;
- documented default behavior.

When multiple presentation layers consume the same model, domain serialization
is the canonical contract unless an adapter is explicitly documented.

## Integration Tests

Integration tests validate collaboration between Atlas layers.

Appropriate examples include:

- CLI to service;
- service to provider;
- provider parsing of controlled subprocess output;
- package compatibility aliases;
- API adapter to domain service;
- persistence adapter to model contract.

Integration tests should remain controlled and should not depend on unrelated
production services.

## Regression Testing

Focused tests run first during development.

The full regression suite must run before completing a sprint when executable
behavior, public contracts, shared infrastructure, compatibility, or
cross-domain behavior changes.

Documentation-only changes may use documentation-specific validation when no
executable behavior changed.

A regression failure must be investigated rather than dismissed because focused
tests pass.

## Runtime Validation

Runtime validation confirms that supported commands and services work in the
actual Atlas environment.

Examples include:

```text
atlas verify
atlas doctor
atlas service list
atlas service doctor
atlas service updates
atlas service history
```

Runtime validation should:

- use safe, supported commands;
- respect read-only and mutation boundaries;
- capture machine-readable output when available;
- parse JSON rather than only checking exit status;
- validate representative real services;
- avoid destructive operations unless explicitly authorized.

Runtime validation complements pytest and does not replace it.

## Compatibility Testing

Compatibility tests are required when preserving or migrating:

- legacy module paths;
- public imports;
- command aliases;
- CLI behavior;
- configuration formats;
- serialized contracts;
- provider defaults.

Compatibility aliases that must preserve monkeypatch targets or module-level
state should be tested for module identity, not merely matching names.

Legacy behavior should be removed only after the canonical replacement is
validated and migration is documented.

## Error Testing

Tests should verify both expected failures and their public representation.

Applicable coverage includes:

- invalid inputs;
- missing identity;
- malformed child contracts;
- provider failures;
- unavailable infrastructure;
- unsupported operations;
- permission failures;
- normalized CLI errors;
- exception cause preservation.

Do not assert fragile implementation-only wording unless wording is part of the
supported public contract.

## Time and Ordering Tests

Tests involving time should use fixed explicit timestamps whenever practical.

Avoid sleep-based testing.

Timestamp tests should verify timezone requirements, UTC normalization, trailing
`Z` serialization, deterministic ordering, duration calculations, and invalid
chronological relationships.

## Test Data and Fixtures

Fixtures should be minimal, explicit, and local to the behavior being tested.

Prefer factory helpers that expose meaningful domain parameters.

Avoid fixtures that silently create broad unrelated state.

Sensitive values, real credentials, private URLs, and production secrets must
never appear in tests or recorded fixtures.

## Test Naming

Test names should state the behavior and expected outcome.

Prefer:

```text
test_inspect_history_translates_unexpected_provider_error
```

over vague names such as:

```text
test_history_error
```

Parameterized tests are appropriate when the same behavior must hold across
multiple inputs.

## Determinism and Isolation

Tests must not depend on execution order, uncontrolled current time, external
network availability, mutable shared state, production credentials, unrelated
containers, or prior manual setup.

Temporary filesystem state should use isolated test directories and be cleaned
automatically.

## Documentation Validation

Documentation changes should validate:

- required files exist;
- local Markdown links resolve;
- required headings or markers exist;
- living-document updates were applied;
- `git diff --check` passes.

Documentation validation does not require the full runtime suite when no
executable behavior changed.

## Repository Validation

Before commit, review:

```text
git status --short
git diff --check
git diff --stat
git diff
```

Untracked files must be reviewed directly because normal `git diff` does not
display their contents.

Generated caches, temporary review bundles, and apply scripts must follow the
documented repository lifecycle.

## Release Audit

Subsystem and release certification may require a formal audit containing:

- compilation;
- shell syntax;
- public API validation;
- compatibility validation;
- documentation validation;
- full regression;
- runtime human-output validation;
- runtime JSON validation;
- repository hygiene review;
- permanent audit summary.

Audit evidence supports certification but does not replace permanent release
documentation.

## Failure Handling

A failing required test blocks completion.

Do not delete or weaken a valid test merely to obtain a passing suite, broadly
skip tests without documented justification, hide failures behind generic
exception handling, or accept flaky behavior as normal.

When a test exposes an in-scope defect, fix the defect before committing.

When a failure is unrelated to the active sprint, document and isolate it
without silently redefining success.

## Test Review Expectations

Review should confirm:

- tests cover approved behavior;
- assertions validate public contracts;
- invalid cases are represented;
- fixtures are deterministic;
- compatibility is tested where applicable;
- runtime validation matches the changed surface;
- the regression decision is appropriate;
- failures are not hidden or ignored.

## Definition of Test Complete

Testing is complete only when every applicable condition is satisfied:

- focused tests pass;
- model, service, provider, and presentation contracts are covered;
- compatibility tests pass;
- regression tests pass when required;
- runtime validation passes when required;
- documentation validation passes;
- repository validation passes;
- known limitations are documented;
- test results are reviewed before commit.

A feature that works manually but lacks appropriate automated and runtime
validation is not complete Atlas work.
ATLAS_M021_5_TESTING_STANDARD_EOF

python3 - <<'PY'
from pathlib import Path


def append_once(path_value: str, marker: str, block: str) -> None:
    path = Path(path_value)
    text = path.read_text()
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + block.strip() + "\n")


path = Path("docs/governance/README.md")
text = path.read_text()
old = "- [ ] `TESTING_STANDARD.md`"
new = "- [x] [`TESTING_STANDARD.md`](TESTING_STANDARD.md)"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("Governance Testing Standard entry not found")
path.write_text(text)

append_once(
    "docs/ENGINEERING_GUIDE.md",
    "## Testing Standard",
    """
## Testing Standard

The canonical Atlas testing requirements are defined in
[`governance/TESTING_STANDARD.md`](governance/TESTING_STANDARD.md).
""",
)

append_once(
    "docs/ENGINEERING_CHECKLIST.md",
    "## Testing Standard Review",
    """
## Testing Standard Review

- [ ] Focused tests cover the approved behavior.
- [ ] Regression testing was run when required.
- [ ] Runtime validation was performed when applicable.
- [ ] Compatibility and repository validation passed.
""",
)

append_once(
    "docs/BUILD_LOG.md",
    "## M-021.5 — Testing Standard",
    """
---

# 2026-08-02

## M-021.5 — Testing Standard

### Completed

- Added the permanent Atlas Testing Standard.
- Formalized unit, model, service, provider, CLI, contract, integration,
  regression, runtime, compatibility, and release-audit validation.
- Linked the Testing Standard from governance and engineering documentation.
- Added testing review gates to the Engineering Checklist.
- Marked the Testing Standard complete in the Roadmap.

### Validation

- Required-section validation.
- Local Markdown-link validation.
- Living-document marker validation.
- `git diff --check`.
""",
)

path = Path("CHANGELOG.md")
text = path.read_text()
entry = (
    "- Added the Atlas Testing Standard governance document defining automated, "
    "runtime, compatibility, repository, and release-audit validation "
    "requirements.\n"
)
if entry not in text:
    anchor = "### Documentation\n\n"
    if anchor not in text:
        raise SystemExit("CHANGELOG Documentation anchor not found")
    path.write_text(text.replace(anchor, anchor + entry, 1))

path = Path("ROADMAP.md")
text = path.read_text()
old = "- [ ] Testing Standard"
new = "- [x] Testing Standard"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("ROADMAP Testing Standard entry not found")
path.write_text(text)
PY

PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

"$PYTHON" - <<'PY'
from pathlib import Path
import re

artifact = Path("docs/governance/TESTING_STANDARD.md")
text = artifact.read_text()

required = (
    "# Atlas Testing Standard",
    "## Testing Philosophy",
    "## Testing Layers",
    "## Unit Tests",
    "## Model Tests",
    "## Service Tests",
    "## Provider Tests",
    "## CLI Tests",
    "## Contract Tests",
    "## Integration Tests",
    "## Regression Testing",
    "## Runtime Validation",
    "## Compatibility Testing",
    "## Documentation Validation",
    "## Repository Validation",
    "## Release Audit",
    "## Failure Handling",
    "## Definition of Test Complete",
)

for heading in required:
    if heading not in text:
        raise SystemExit(f"Missing Testing Standard heading: {heading}")

documents = (
    artifact,
    Path("docs/governance/README.md"),
    Path("docs/ENGINEERING_GUIDE.md"),
    Path("docs/ENGINEERING_CHECKLIST.md"),
    Path("docs/BUILD_LOG.md"),
    Path("CHANGELOG.md"),
    Path("ROADMAP.md"),
)

link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
failures = []

for document in documents:
    content = document.read_text()
    for target in link_pattern.findall(content):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        local = target.split("#", 1)[0]
        if not local:
            continue
        resolved = (document.parent / local).resolve()
        if not resolved.exists():
            failures.append(f"{document}: broken link -> {target}")

if failures:
    raise SystemExit("\n".join(failures))

print("M-021.5 Testing Standard validated.")
PY

git diff --check

printf '\nM-021.5 Testing Standard applied successfully.\n'
printf 'Backup: %s\n' "$BACKUP_DIR"
printf '\nReview with:\n'
printf '  sed -n "1,420p" docs/governance/TESTING_STANDARD.md\n'
printf '  git status --short\n'
printf '  git diff --check\n'
printf '  git diff --stat\n'
