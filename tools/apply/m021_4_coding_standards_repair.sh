#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.4-coding-standards-repair-$STAMP"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -d "$ROOT/.git" ]] || die "Not a Git repository: $ROOT"
cd "$ROOT"

[[ -f docs/governance/CODING_STANDARDS.md ]] || \
  die "Expected existing Coding Standards file"

mkdir -p "$BACKUP_DIR/docs/governance"
cp -a \
  docs/governance/CODING_STANDARDS.md \
  "$BACKUP_DIR/docs/governance/CODING_STANDARDS.md"

cat <<'ATLAS_CODING_STANDARDS_EOF' > docs/governance/CODING_STANDARDS.md
# Atlas Coding Standards

## Purpose

This document defines the canonical coding standards for Project Atlas.

These standards turn the principles of the
[Engineering Charter](ENGINEERING_CHARTER.md) into concrete implementation
requirements. They apply to new code, refactors, compatibility work, tests, and
public interfaces.

Atlas favors readable, explicit, deterministic, and maintainable code over
clever or unnecessarily abstract implementations.

## General Principles

Atlas code should be:

- readable before clever;
- explicit rather than dependent on hidden behavior;
- deterministic wherever practical;
- organized around clear ownership;
- small enough to understand and test;
- consistent with existing public contracts;
- safe to evolve incrementally;
- documented at the appropriate public boundary.

Avoid introducing abstractions until they solve a demonstrated problem.

Prefer extending an established pattern over creating a competing pattern.

## Source Organization

Code should be grouped by domain and responsibility.

A mature domain may contain:

```text
atlas/<domain>/
├── __init__.py
├── models.py
├── provider.py
├── providers/
└── services/
```

Additional files or packages are appropriate when they represent a distinct,
cohesive responsibility.

Do not create layers solely to satisfy a preferred directory structure.

### Module responsibilities

- **Models** define normalized domain contracts.
- **Services** orchestrate domain behavior and validation.
- **Providers** isolate infrastructure-specific behavior.
- **Presentation layers** render or transport domain results.
- **Compatibility modules** preserve supported legacy imports during migration.

Presentation code must not duplicate service or provider logic.

## Public APIs

Public interfaces must be intentional.

Public models, services, providers, enums, errors, and reports should be
exported through the owning package's `__init__.py` when they are part of the
supported domain API.

The `__all__` declaration should remain synchronized with public imports when
the package uses one.

Internal helpers should remain private unless a stable external contract is
required.

Avoid exposing infrastructure-native responses as public Atlas contracts.

## Domain Models

Public domain models should follow a consistent contract.

Every applicable public model must:

- normalize inputs;
- validate its own identity;
- validate child contracts;
- normalize timestamps;
- reject invalid state combinations;
- provide deterministic `to_dict()` serialization;
- have a dedicated test suite;
- be exported through its package interface.

### Input normalization

Normalize inputs at the model boundary rather than requiring every caller to
perform identical cleanup.

Examples include:

- trimming surrounding whitespace;
- normalizing identifiers to their canonical case;
- converting supported enum strings into enum members;
- normalizing collections into immutable tuples;
- copying mappings to prevent external mutation;
- converting timestamps to canonical UTC form.

Normalization must not silently reinterpret invalid data.

### Identity validation

Identifiers must use documented validation rules.

A model must not accept an empty, malformed, or ambiguous identity merely
because a downstream provider might tolerate it.

Related child objects must agree on identity where the contract requires it.

### Child-contract validation

A parent model must verify that its children are instances of the expected
domain type.

Do not assume that an iterable contains valid children.

Where duplicate children or conflicting identities are invalid, reject them
explicitly.

### Timestamp normalization

Public timestamps should:

- use ISO 8601;
- include timezone information;
- normalize to UTC;
- serialize with a trailing `Z`;
- reject naive timestamps unless a contract explicitly permits them.

Ordering and duration calculations must use normalized timestamp values.

### Immutability

Domain contracts should be immutable when practical.

Use frozen dataclasses or equivalent behavior for values intended to represent
an observation, decision, report, or historical record.

Mutable internal implementation state should not leak through public models.

### Serialization

Every public model intended for CLI, API, persistence, events, or Portal use
should provide `to_dict()`.

Serialization should be:

- deterministic;
- composed only of JSON-compatible values;
- stable across presentation layers;
- explicit about null values;
- based on normalized data;
- free of provider-native objects.

A CLI or API should normally serialize the domain model directly rather than
constructing a second competing schema.

## Services

Services own provider-independent orchestration.

A service should:

- validate its dependencies;
- normalize requested identity through established domain paths;
- invoke providers through documented interfaces;
- validate provider return contracts;
- enforce cross-object identity consistency;
- preserve known Atlas domain errors;
- translate unexpected provider failures;
- return normalized domain models or reports;
- remain independent of CLI, HTTP, templates, and other presentation concerns.

Services should not:

- print output;
- parse command-line arguments;
- render HTML;
- depend directly on Docker when a provider abstraction exists;
- return raw provider responses;
- duplicate model validation.

Service methods should have narrow, predictable responsibilities.

## Providers

Providers isolate external systems and infrastructure.

A provider should:

- implement the documented provider contract;
- translate infrastructure data into Atlas domain models;
- keep subprocess, Docker, filesystem, network, and registry behavior behind
  the provider boundary;
- validate enough external data to create trustworthy normalized contracts;
- use conservative classifications when information cannot be verified;
- preserve the subsystem's documented read-only or mutation boundary.

Providers should not:

- format CLI output;
- make user-interface decisions;
- return raw dictionaries when a domain contract exists;
- claim facts that cannot be verified from the available provider data.

Concrete default methods may be used to preserve compatibility when they return
safe, valid, and documented behavior.

## CLI Standards

The CLI is a presentation layer over domain services.

CLI commands should:

- use domain services rather than providers directly;
- provide concise human-readable output;
- support canonical JSON where required;
- write successful output to standard output;
- write errors to standard error;
- return documented exit codes;
- use consistent command and option naming;
- preserve supported legacy commands when practical.

### JSON output

JSON output should:

- serialize canonical domain contracts;
- remain machine-readable and deterministic;
- avoid human-only labels or formatting;
- use normalized field names and timestamps;
- end with a newline;
- be covered by contract tests.

Do not maintain separate CLI-only JSON schemas unless a documented adapter is
required.

### Error behavior

Known Atlas errors should produce concise, normalized messages.

Unexpected provider or infrastructure failures should be translated before they
reach the presentation layer.

Tracebacks should not be exposed during normal supported CLI usage.

## Compatibility and Migration

Atlas follows evolution over replacement.

When changing public behavior:

- extend before replacing;
- refactor before rewriting;
- preserve supported imports and commands when practical;
- use compatibility aliases or adapters where appropriate;
- validate legacy and canonical paths;
- document migration requirements;
- remove legacy behavior only after the replacement is validated.

A compatibility module that must preserve monkeypatch targets or module-level
state should resolve to the canonical module object rather than only copying
selected names.

Breaking changes require explicit design review and appropriate documentation.

## Error Contracts

Domain-specific failures should use the owning Atlas error hierarchy.

Raise errors at the boundary where invalid state is detected.

Do not use broad exception handling to hide programming errors.

When translating an unexpected provider exception:

- preserve the original exception as the cause;
- provide a concise Atlas-level message;
- include normalized identity when it materially aids diagnosis;
- avoid leaking secrets or unsafe infrastructure details.

## Functions and Methods

Functions and methods should:

- have one primary responsibility;
- use descriptive names;
- return predictable types;
- validate public inputs;
- avoid unnecessary side effects;
- keep branching understandable;
- use type annotations where the surrounding codebase does.

Prefer early validation over deeply nested control flow.

Private helpers should express a meaningful sub-responsibility rather than
merely shortening a function.

## Imports

Imports should be explicit and organized consistently with the existing module.

Avoid wildcard imports.

Use package-relative imports within a domain when they make ownership clear.

Avoid circular dependencies by preserving domain layering rather than relying
on delayed or conditional imports as the default solution.

## Shell Code

Atlas shell code should use:

```bash
set -Eeuo pipefail
```

when appropriate for the script's execution model.

Shell scripts should:

- validate required paths and state;
- quote variable expansions;
- fail with concise error messages;
- avoid destructive behavior without explicit safeguards;
- use guarded heredocs for complete file replacements when practical;
- create backups before modifying important files;
- remain idempotent where practical;
- print clear review or validation instructions.

Living documents should generally be updated through guarded insertion points
rather than full rewrites.

## Tests

Every new public contract requires dedicated tests at the appropriate layer.

Code-level tests should cover:

- normalization;
- valid construction;
- invalid identity;
- invalid child contracts;
- timestamp behavior;
- deterministic serialization;
- immutability when required;
- provider result validation;
- error preservation and translation;
- public exports;
- compatibility paths;
- human and JSON CLI behavior where applicable.

Tests should be:

- deterministic;
- isolated;
- clearly named;
- readable without depending on implementation trivia;
- focused on one behavior;
- free of unnecessary timing or network dependencies.

The broader testing lifecycle is defined in the Testing Standard.

## Documentation Requirements

Implementation is not code-complete until applicable documentation is updated.

Depending on the change, this can include:

- architecture documentation;
- CLI documentation;
- API documentation;
- engineering specifications;
- ADRs;
- `docs/BUILD_LOG.md`;
- `CHANGELOG.md`;
- `ROADMAP.md`;
- release certification.

Documentation must describe the actual implemented contract, including safety
boundaries and intentional limitations.

## Code Review Expectations

Review should confirm:

- scope matches the approved sprint;
- public contracts follow Atlas conventions;
- duplicated logic was not introduced;
- compatibility was preserved or documented;
- validation exists at the correct layer;
- tests cover the new behavior;
- documentation matches implementation;
- repository hygiene remains acceptable;
- `git diff --check` passes.

Review feedback that expands the active scope should normally be deferred unless
it identifies a defect, blocker, compatibility issue, or safety concern.

## Definition of Code Complete

Code is complete only when every applicable requirement is satisfied:

- implementation matches approved scope;
- public contracts are normalized and validated;
- focused tests pass;
- regression tests pass;
- runtime validation passes when required;
- documentation is complete;
- compatibility is preserved or migration is documented;
- repository review passes;
- the change is committed;
- the change is pushed.

Locally functioning code without tests, documentation, review, commit, and push
is not complete Atlas work.
ATLAS_CODING_STANDARDS_EOF

PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

"$PYTHON" - <<'PY'
from pathlib import Path

path = Path("docs/governance/CODING_STANDARDS.md")
text = path.read_text()

required = (
    "# Atlas Coding Standards",
    "## Public APIs",
    "## Domain Models",
    "### Timestamp normalization",
    "### Serialization",
    "## Services",
    "## Providers",
    "## CLI Standards",
    "## Compatibility and Migration",
    "## Error Contracts",
    "## Shell Code",
    "## Tests",
    "## Documentation Requirements",
    "## Definition of Code Complete",
)

for heading in required:
    if heading not in text:
        raise SystemExit(f"Missing Coding Standards section: {heading}")

print("Complete Atlas Coding Standards validated.")
PY

git diff --check

printf '\nM-021.4 Coding Standards repair applied successfully.\n'
printf 'Backup: %s\n' "$BACKUP_DIR"
printf '\nReview with:\n'
printf '  sed -n "1,420p" docs/governance/CODING_STANDARDS.md\n'
printf '  git diff --check\n'
printf '  git status --short\n'
