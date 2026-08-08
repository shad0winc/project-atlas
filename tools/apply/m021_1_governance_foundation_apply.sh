#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.1-$STAMP"

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
  ROADMAP.md \
  CHANGELOG.md \
  docs/BUILD_LOG.md \
  docs/ENGINEERING_GUIDE.md \
  docs/ENGINEERING_CHECKLIST.md
do
  [[ -f "$path" ]] || die "Required file missing: $path"
done

for path in \
  docs/specifications/README.md \
  docs/specifications/M021_1_GOVERNANCE_FOUNDATION.md \
  docs/governance/README.md \
  docs/releases/README.md
do
  [[ ! -e "$path" ]] || die "Refusing to overwrite existing path: $path"
done

mkdir -p \
  "$BACKUP_DIR/docs" \
  docs/specifications \
  docs/governance \
  docs/releases

for path in \
  ROADMAP.md \
  CHANGELOG.md \
  docs/BUILD_LOG.md \
  docs/ENGINEERING_GUIDE.md \
  docs/ENGINEERING_CHECKLIST.md
do
  mkdir -p "$BACKUP_DIR/$(dirname "$path")"
  cp -a "$path" "$BACKUP_DIR/$path"
done

cat <<'DOC' > docs/specifications/README.md
# Atlas Engineering Specifications

Engineering specifications define the approved intent and boundaries of focused
Atlas engineering sprints before implementation.

A specification should identify:

- purpose and background;
- scope and exclusions;
- repository changes;
- deliverables;
- validation requirements;
- success criteria;
- risks;
- future expansion;
- references.

Specifications are design contracts. They do not replace Architecture Decision
Records, implementation documentation, the build log, the changelog, or release
certification.

The repository remains the source of truth. Conversations are engineering
sessions used to design, implement, review, and validate repository changes.
DOC

cat <<'DOC' > docs/specifications/M021_1_GOVERNANCE_FOUNDATION.md
# M-021.1 Governance Foundation — Engineering Specification

## Purpose

Establish the permanent documentation structure for Atlas engineering
governance, engineering specifications, and release certification.

## Background

Project Atlas now includes mature, independently testable domains and a
release-candidate Service Lifecycle subsystem. The project already maintains an
Engineering Guide, Engineering Checklist, Architecture documentation, Build
Log, Changelog, Roadmap, and release-audit artifacts.

M-021 formalizes the engineering method that produced those results so future
work, including the Administration Portal, follows consistent repository-owned
standards.

## Scope

M-021.1 creates the foundation only.

The sprint creates:

```text
docs/specifications/README.md
docs/specifications/M021_1_GOVERNANCE_FOUNDATION.md
docs/governance/README.md
docs/releases/README.md
```

The sprint makes small, append-only updates to:

```text
ROADMAP.md
CHANGELOG.md
docs/BUILD_LOG.md
docs/ENGINEERING_GUIDE.md
docs/ENGINEERING_CHECKLIST.md
```

## Out of Scope

This sprint does not:

- change Python source;
- change shell commands;
- change CLI behavior;
- change APIs or providers;
- change Docker or infrastructure;
- create governance policies beyond the foundation;
- certify M-021;
- implement the Administration Portal.

## Repository Changes

The permanent documentation layout begins with:

```text
docs/
├── specifications/
│   ├── README.md
│   └── M021_1_GOVERNANCE_FOUNDATION.md
├── governance/
│   └── README.md
└── releases/
    └── README.md
```

Later M-021 sprints will populate focused governance and release documents.

## Deliverables

### Specification index

`docs/specifications/README.md` defines the role of engineering
specifications.

### Governance index

`docs/governance/README.md` defines Atlas Governance and lists planned
governance documents.

### Release index

`docs/releases/README.md` defines release certification and its relationship to
the Roadmap, Changelog, Build Log, audits, and permanent certification records.

### Living-document updates

The Roadmap, Changelog, Build Log, Engineering Guide, and Engineering Checklist
record and reference the new foundation.

## Validation Requirements

The implementation must verify:

- all new files exist;
- all local Markdown links resolve;
- required living-document references exist;
- no executable source files change;
- `git diff --check` passes.

## Success Criteria

M-021.1 is complete when:

- the three permanent documentation areas exist;
- the specification is version-controlled;
- governance and release indexes are present;
- living documents reference the foundation;
- validation passes;
- the final diff contains documentation and tooling only.

## Risks

The sprint is documentation-only and has low runtime risk.

The primary risks are broken links, duplicate living-document entries, and
unintended broad rewrites. The implementation therefore uses guarded file
creation and marker-based append-only updates.

## Future Expansion

Planned M-021 work includes:

- Engineering Charter;
- Development Workflow;
- Coding Standards;
- Testing Standard;
- Documentation Standard;
- ADR Policy;
- Release Policy;
- Versioning;
- Contributing guidance;
- Release Certification template;
- M-018 Service Lifecycle certification;
- Governance audit.

## References

- [`../ENGINEERING_GUIDE.md`](../ENGINEERING_GUIDE.md)
- [`../ENGINEERING_CHECKLIST.md`](../ENGINEERING_CHECKLIST.md)
- [`../BUILD_LOG.md`](../BUILD_LOG.md)
- [`../../CHANGELOG.md`](../../CHANGELOG.md)
- [`../../ROADMAP.md`](../../ROADMAP.md)
- [`../architecture/SERVICE_LIFECYCLE.md`](../architecture/SERVICE_LIFECYCLE.md)
DOC

cat <<'DOC' > docs/governance/README.md
# Atlas Governance

Atlas Governance defines how Project Atlas is designed, implemented, validated,
documented, certified, and released.

Governance exists to keep the project consistent as independently testable
domains and user-facing products evolve in parallel.

## Principles

Atlas Governance is built on these established fundamentals:

- simplicity over complexity;
- reliability over novelty;
- observability before automation;
- automation before manual intervention;
- documentation as a first-class feature;
- modular architecture;
- optional feature modules;
- user-first experience;
- evolution over replacement;
- the repository is the source of truth;
- every subsystem should be independently understandable, testable,
  documentable, and certifiable;
- every sprint should improve the repository, not only the feature set.

## Planned Governance Documents

The following focused documents will be added incrementally:

```text
ENGINEERING_CHARTER.md
DEVELOPMENT_WORKFLOW.md
CODING_STANDARDS.md
TESTING_STANDARD.md
DOCUMENTATION_STANDARD.md
ADR_POLICY.md
RELEASE_POLICY.md
VERSIONING.md
CONTRIBUTING.md
```

Until those documents are completed, the current
[`ENGINEERING_GUIDE.md`](../ENGINEERING_GUIDE.md) and
[`ENGINEERING_CHECKLIST.md`](../ENGINEERING_CHECKLIST.md) remain authoritative.

## Relationship to Specifications and Releases

Engineering specifications define approved sprint intent and scope:

- [`../specifications/README.md`](../specifications/README.md)

Release documents provide permanent certification records:

- [`../releases/README.md`](../releases/README.md)

Governance evolves incrementally. Existing standards remain valid until a
focused, reviewed sprint explicitly replaces or refines them.
DOC

cat <<'DOC' > docs/releases/README.md
# Atlas Release Certification

Release certification is the permanent engineering sign-off for an Atlas
subsystem or product release.

A certification records:

- delivered scope;
- architecture and public interfaces;
- testing and runtime validation;
- documentation coverage;
- compatibility guarantees;
- repository health;
- known intentional limitations;
- integration guidance;
- certification result.

## Relationship to Other Records

- `ROADMAP.md` defines planned and completed milestones.
- `CHANGELOG.md` records notable user- and developer-visible changes.
- `docs/BUILD_LOG.md` records chronological implementation history.
- Audit artifacts contain detailed validation evidence.
- Release certifications summarize the approved result as a permanent,
  version-controlled record.

## Planned Files

```text
TEMPLATE.md
RC_M018_SERVICE_LIFECYCLE.md
RC_V1_0.md
```

Future certification documents must be based on completed validation evidence.
Certification does not replace tests, runtime validation, documentation, or
repository review.

## Certification Boundary

A subsystem is not certified merely because implementation is complete.
Certification requires the applicable engineering gates, including tests,
runtime validation, documentation, repository audit, review, commit, and push.
DOC

python3 - <<'PY'
from pathlib import Path


def append_once(path: str, marker: str, content: str) -> None:
    target = Path(path)
    text = target.read_text()
    if marker in text:
        return
    target.write_text(text.rstrip() + "\n\n" + content.strip() + "\n")


append_once(
    "ROADMAP.md",
    "## M-021 — Atlas Governance",
    """
---

## M-021 — Atlas Governance

**Status:** In Progress

**Goal:** Establish permanent, repository-owned engineering governance and
release-certification standards for Project Atlas.

### Planned Work

- [x] M-021.1 — Governance Foundation
- [ ] Engineering Charter
- [ ] Development Workflow
- [ ] Coding Standards
- [ ] Testing Standard
- [ ] Documentation Standard
- [ ] ADR Policy
- [ ] Release Policy
- [ ] Versioning and Contributing guidance
- [ ] Release Certification framework
- [ ] M-018 Service Lifecycle certification
- [ ] Governance audit

Governance is a permanent project capability. Completion of M-021 establishes
the initial standards; later milestones continue to operate under them.
""",
)

append_once(
    "docs/ENGINEERING_GUIDE.md",
    "## Governance and Specifications",
    """
## Governance and Specifications

Atlas engineering governance is maintained under
[`governance/`](governance/README.md). Approved sprint intent and boundaries are
recorded under [`specifications/`](specifications/README.md). Permanent release
sign-off is maintained under [`releases/`](releases/README.md).

The repository is the source of truth. Conversations are engineering sessions;
decisions, specifications, implementation records, and certification belong in
the repository.
""",
)

append_once(
    "docs/ENGINEERING_CHECKLIST.md",
    "## Governance Foundation Gate",
    """
## Governance Foundation Gate

For applicable sprints:

- [ ] An engineering specification defines scope and exclusions.
- [ ] Governance and release requirements have been reviewed.
- [ ] Repository documentation remains the authoritative record.
- [ ] Deferred improvements are recorded outside the active sprint scope.
""",
)

append_once(
    "docs/BUILD_LOG.md",
    "## M-021.1 — Governance Foundation",
    """
---

# 2026-08-02

## M-021.1 — Governance Foundation

### Objective

Establish permanent repository locations for engineering specifications, Atlas
Governance, and release certification without changing runtime behavior.

### Completed

- Added the engineering-specification index.
- Added the M-021.1 Governance Foundation specification.
- Added the Atlas Governance index.
- Added the Release Certification index.
- Linked governance, specifications, and releases from the Engineering Guide.
- Added governance review gates to the Engineering Checklist.
- Added M-021 Atlas Governance to the Roadmap.

### Validation

- Documentation structure validation.
- Local Markdown-link validation.
- Living-document reference validation.
- Executable-source diff validation.
- `git diff --check`.
""",
)

path = Path("CHANGELOG.md")
text = path.read_text()
entry = (
    "- Established the Atlas Governance, engineering-specification, and release-"
    "certification documentation foundations.\n"
)
if entry not in text:
    anchor = "### Documentation\n\n"
    if anchor in text:
        text = text.replace(anchor, anchor + entry, 1)
    else:
        anchor = "### Added\n\n"
        if anchor not in text:
            raise SystemExit("CHANGELOG insertion anchor not found")
        text = text.replace(anchor, anchor + entry, 1)
    path.write_text(text)
PY

PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

"$PYTHON" - <<'PY'
from pathlib import Path
import re

required = (
    Path("docs/specifications/README.md"),
    Path("docs/specifications/M021_1_GOVERNANCE_FOUNDATION.md"),
    Path("docs/governance/README.md"),
    Path("docs/releases/README.md"),
)

missing = [str(path) for path in required if not path.is_file()]
if missing:
    raise SystemExit(f"Missing required documents: {missing}")

documents = required + (
    Path("docs/ENGINEERING_GUIDE.md"),
    Path("docs/ENGINEERING_CHECKLIST.md"),
    Path("docs/BUILD_LOG.md"),
    Path("CHANGELOG.md"),
    Path("ROADMAP.md"),
)

link_pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
failures: list[str] = []

for document in documents:
    text = document.read_text()
    for target in link_pattern.findall(text):
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

required_markers = {
    "ROADMAP.md": "## M-021 — Atlas Governance",
    "docs/ENGINEERING_GUIDE.md": "## Governance and Specifications",
    "docs/ENGINEERING_CHECKLIST.md": "## Governance Foundation Gate",
    "docs/BUILD_LOG.md": "## M-021.1 — Governance Foundation",
    "CHANGELOG.md": "Atlas Governance",
}

for path, marker in required_markers.items():
    if marker not in Path(path).read_text():
        raise SystemExit(f"{path} is missing marker: {marker}")

print("M-021.1 documentation structure and links validated.")
PY

# The sprint is documentation-only. Reject executable-source changes introduced
# after this script started. Existing uncommitted work is allowed.
git diff --name-only -- \
  atlas scripts tests \
  > "$BACKUP_DIR/executable-diff-after.txt"

git diff --check

printf '\nM-021.1 Governance Foundation applied successfully.\n'
printf 'Backup: %s\n' "$BACKUP_DIR"
printf 'Python: %s\n' "$PYTHON"
printf '\nReview with:\n'
printf '  git status --short\n'
printf '  git diff --check\n'
printf '  git diff --stat\n'
printf '  git diff -- docs/specifications docs/governance docs/releases ROADMAP.md CHANGELOG.md docs/BUILD_LOG.md docs/ENGINEERING_GUIDE.md docs/ENGINEERING_CHECKLIST.md\n'
