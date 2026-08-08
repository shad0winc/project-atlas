#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.2-$STAMP"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

[[ -d "$ROOT/.git" ]] || die "Not a Git repository: $ROOT"
cd "$ROOT"

BRANCH="$(git branch --show-current)"
[[ "$BRANCH" == "feature/public-ingress" ]] || \
  die "Expected feature/public-ingress; found: ${BRANCH:-detached}"

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

[[ ! -e docs/governance/ENGINEERING_CHARTER.md ]] || \
  die "Refusing to overwrite existing charter"

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

cat <<'DOC' > docs/governance/ENGINEERING_CHARTER.md
# Project Atlas Engineering Charter

## Mission

Project Atlas is an intelligent, modular, self-hosted entertainment platform
built first for trusted friends and family.

Atlas exists to make self-hosted services easier to operate, understand, and
use without requiring every user or administrator to understand the underlying
infrastructure.

Engineering decisions must support:

- dependable day-to-day operation;
- clear and maintainable implementation;
- safe evolution over time;
- understandable behavior;
- practical usability;
- long-term ownership.

## Vision

Atlas should evolve as a durable platform rather than a collection of scripts
or tightly coupled applications.

Core domains should remain reusable across:

- command-line interfaces;
- APIs;
- administrative interfaces;
- user-facing portals;
- automation;
- future optional modules.

Products should consume stable platform contracts rather than duplicate domain
logic or communicate directly with infrastructure when a supported abstraction
exists.

## Core Engineering Principles

### Simplicity over complexity

Prefer clear, direct designs that are easy to understand, test, operate, and
maintain.

Avoid clever implementations that add hidden behavior, unnecessary
abstractions, or maintenance cost without a demonstrated benefit.

### Reliability over novelty

Stable and predictable behavior is more valuable than experimental capability.

New technology and design patterns should be adopted only when they materially
improve Atlas without weakening reliability, operability, or maintainability.

### Observability before automation

Atlas must measure, inspect, and explain system behavior before it acts
automatically.

Automated decisions should be traceable to normalized inputs, explicit policy,
and observable system state.

### Automation before manual intervention

Once behavior is understood and trusted, repetitive operational work should be
automated.

Automation should reduce operational burden without introducing unexpected or
irreversible behavior.

### Documentation as a first-class feature

Documentation is part of the deliverable.

A feature, subsystem, or milestone is not complete until its relevant
architecture, API, CLI, operational, and release documentation is updated.

### Modular architecture

Components should be loosely coupled, independently testable, and organized
around clear public contracts.

Core functionality should remain small and stable. Cross-domain dependencies
must be explicit.

### Optional feature modules

Advanced or environment-specific functionality should be optional whenever
practical.

The core platform should remain useful, understandable, and maintainable
without requiring every optional module.

### User-first experience

Internal elegance must not come at the expense of usability.

Friends, family, and administrators should be able to use supported Atlas
workflows without understanding the implementation.

### Evolution over replacement

Atlas should improve incrementally.

When changing an existing capability:

- extend before replacing;
- refactor before rewriting;
- preserve compatibility whenever practical;
- migrate incrementally;
- validate the replacement before removing legacy behavior.

## Repository Philosophy

The Git repository is the source of truth.

Conversations are engineering sessions. Decisions and deliverables must be
captured in repository-owned artifacts when they are intended to outlive the
session.

The repository should contain the authoritative versions of:

- source code;
- tests;
- engineering specifications;
- architecture decisions;
- governance;
- operational documentation;
- release records;
- roadmap status;
- build history;
- changelog entries.

Temporary development artifacts should have an explicit lifecycle and should
not remain in active repository locations after their purpose is complete.

## Subsystem Independence

Every Atlas subsystem should be independently:

- understandable;
- testable;
- documentable;
- certifiable.

A subsystem should expose clear public contracts and avoid requiring consumers
to understand internal providers, persistence, infrastructure, or unrelated
domains.

Subsystems should be replaceable or extendable behind stable interfaces when
practical.

## Public Contract Standards

Public models and reports should:

- normalize inputs;
- validate identity;
- validate child contracts;
- normalize timestamps;
- provide deterministic serialization;
- expose documented public imports;
- have dedicated tests.

Public services should:

- own orchestration and domain validation;
- preserve known Atlas errors;
- translate unexpected provider failures;
- remain independent of presentation layers;
- avoid duplicating provider logic.

Providers should:

- isolate infrastructure-specific behavior;
- return normalized domain contracts;
- avoid leaking raw infrastructure responses into higher layers;
- preserve the documented safety boundary.

## Development Lifecycle

Atlas engineering sprints follow this lifecycle:

```text
Review repository state
↓
Review architecture and dependencies
↓
Confirm specification and scope
↓
Design the change
↓
Implement incrementally
↓
Validate compatibility
↓
Run focused tests
↓
Run regression tests
↓
Perform runtime validation when applicable
↓
Update documentation
↓
Review repository state
↓
Commit
↓
Push
```

Release certification and audit are added when required by the milestone or
release policy.

Once sprint scope is approved, additional improvements should be deferred
unless a concrete blocker, defect, compatibility issue, or safety concern
requires action.

## Definition of Done

A sprint is complete only when every applicable requirement is satisfied:

- approved scope is implemented;
- public contracts are complete and stable;
- compatibility is preserved or migration is documented;
- focused validation passes;
- regression validation passes;
- runtime validation passes when applicable;
- documentation is complete;
- `BUILD_LOG.md` is updated when appropriate;
- `CHANGELOG.md` is updated when appropriate;
- `ROADMAP.md` is updated when appropriate;
- repository review passes;
- temporary tooling is archived or assigned an explicit lifecycle;
- the change is committed;
- the change is pushed.

Uncommitted implementation is progress, not completion.

## Engineering Discipline

Every sprint should leave the repository in a better state than it found it.

Improvement may include:

- simpler architecture;
- clearer ownership;
- stronger tests;
- better documentation;
- cleaner tooling;
- reduced duplication;
- more consistent contracts;
- safer operation.

Repository cleanup must not remove useful history without preserving it in an
approved archive or permanent record.

## Safety and Change Boundaries

Infrastructure mutations require stronger validation than read-only
inspection.

Potentially destructive or service-affecting operations should include
appropriate safeguards such as:

- identity validation;
- dependency validation;
- backup;
- health validation;
- maintenance records;
- rollback strategy;
- explicit authorization.

Read-only observation should precede automated mutation.

## Long-Term Direction

Atlas should continue evolving from a stable core platform into focused
products.

The Administration Portal, user-facing portals, APIs, and future modules should
consume existing domain services and normalized contracts.

Future capability should extend the platform without weakening the principles
in this Charter.

## Charter Governance

This Charter is intended to remain stable.

Changes should be:

- deliberate;
- documented;
- reviewed against existing Atlas behavior;
- recorded in the Build Log and Changelog when appropriate;
- made only when the engineering philosophy has genuinely evolved.

Detailed implementation standards belong in focused governance documents. This
Charter defines the principles those standards must preserve.
DOC

python3 - <<'PY'
from pathlib import Path


def append_once(path: str, marker: str, content: str) -> None:
    target = Path(path)
    text = target.read_text()
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n" + content.strip() + "\n")


path = Path("docs/governance/README.md")
text = path.read_text()
planned = "ENGINEERING_CHARTER.md"
if planned not in text:
    raise SystemExit(
        "Governance README does not contain the planned charter entry"
    )

text = text.replace(
    "ENGINEERING_CHARTER.md",
    "[`ENGINEERING_CHARTER.md`](ENGINEERING_CHARTER.md)",
    1,
)
path.write_text(text)

append_once(
    "docs/ENGINEERING_GUIDE.md",
    "## Engineering Charter",
    """
## Engineering Charter

The permanent engineering principles for Project Atlas are defined in the
[`Engineering Charter`](governance/ENGINEERING_CHARTER.md).

The Charter governs the detailed standards in this guide. When a local practice
conflicts with the Charter, the conflict must be resolved explicitly rather
than silently bypassing the Charter.
""",
)

append_once(
    "docs/ENGINEERING_CHECKLIST.md",
    "## Engineering Charter Review",
    """
## Engineering Charter Review

- [ ] The sprint preserves the Atlas Engineering Charter.
- [ ] Scope remained locked after approval unless a concrete blocker or defect required change.
- [ ] The repository is the authoritative record of durable decisions.
- [ ] The sprint leaves the repository more maintainable than it found it.
""",
)

append_once(
    "docs/BUILD_LOG.md",
    "## M-021.2 — Engineering Charter",
    """
---

# 2026-08-02

## M-021.2 — Engineering Charter

### Objective

Create the permanent engineering constitution for Project Atlas and link it
from the existing governance and engineering documentation.

### Completed

- Added `docs/governance/ENGINEERING_CHARTER.md`.
- Formalized the Atlas mission and platform vision.
- Formalized the core engineering principles.
- Formalized the repository-as-source-of-truth philosophy.
- Formalized subsystem independence and public-contract expectations.
- Formalized the engineering lifecycle and definition of done.
- Added Charter review gates to the Engineering Checklist.
- Linked the Charter from the Governance index and Engineering Guide.

### Validation

- Documentation existence validation.
- Local Markdown-link validation.
- Required Charter-section validation.
- Living-document marker validation.
- `git diff --check`.
""",
)

path = Path("CHANGELOG.md")
text = path.read_text()
entry = (
    "- Added the Project Atlas Engineering Charter, formalizing the project's "
    "mission, engineering principles, repository philosophy, subsystem "
    "standards, development lifecycle, and definition of done.\n"
)
if entry not in text:
    anchor = "### Documentation\n\n"
    if anchor not in text:
        raise SystemExit("CHANGELOG Documentation anchor not found")
    text = text.replace(anchor, anchor + entry, 1)
    path.write_text(text)

path = Path("ROADMAP.md")
text = path.read_text()
old = "- [ ] Engineering Charter"
new = "- [x] Engineering Charter"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("ROADMAP Engineering Charter checklist entry not found")
path.write_text(text)
PY

PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

"$PYTHON" - <<'PY'
from pathlib import Path
import re

charter = Path("docs/governance/ENGINEERING_CHARTER.md")
if not charter.is_file():
    raise SystemExit("Engineering Charter was not created")

text = charter.read_text()
required_headings = (
    "# Project Atlas Engineering Charter",
    "## Mission",
    "## Vision",
    "## Core Engineering Principles",
    "## Repository Philosophy",
    "## Subsystem Independence",
    "## Public Contract Standards",
    "## Development Lifecycle",
    "## Definition of Done",
    "## Engineering Discipline",
    "## Safety and Change Boundaries",
    "## Long-Term Direction",
    "## Charter Governance",
)
for heading in required_headings:
    if heading not in text:
        raise SystemExit(f"Charter is missing heading: {heading}")

documents = (
    charter,
    Path("docs/governance/README.md"),
    Path("docs/ENGINEERING_GUIDE.md"),
    Path("docs/ENGINEERING_CHECKLIST.md"),
    Path("docs/BUILD_LOG.md"),
    Path("CHANGELOG.md"),
    Path("ROADMAP.md"),
)

link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
failures: list[str] = []

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

markers = {
    "docs/governance/README.md": "ENGINEERING_CHARTER.md",
    "docs/ENGINEERING_GUIDE.md": "## Engineering Charter",
    "docs/ENGINEERING_CHECKLIST.md": "## Engineering Charter Review",
    "docs/BUILD_LOG.md": "## M-021.2 — Engineering Charter",
    "CHANGELOG.md": "Project Atlas Engineering Charter",
    "ROADMAP.md": "- [x] Engineering Charter",
}
for path, marker in markers.items():
    if marker not in Path(path).read_text():
        raise SystemExit(f"{path} is missing marker: {marker}")

print("M-021.2 Engineering Charter documentation validated.")
PY

git diff --check

printf '\nM-021.2 Engineering Charter applied successfully.\n'
printf 'Backup: %s\n' "$BACKUP_DIR"
printf 'Python: %s\n' "$PYTHON"
printf '\nReview with:\n'
printf '  git status --short\n'
printf '  git diff --check\n'
printf '  git diff --stat\n'
printf '  git diff -- docs/governance/ENGINEERING_CHARTER.md docs/governance/README.md docs/ENGINEERING_GUIDE.md docs/ENGINEERING_CHECKLIST.md docs/BUILD_LOG.md CHANGELOG.md ROADMAP.md\n'
