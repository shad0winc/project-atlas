#!/usr/bin/env bash
#
# ==============================================================================
# Project Atlas
# Sprint: M-021.6
# Artifact: Documentation Standard
# Purpose: Install the canonical Documentation Standard and update governance.
# Runtime Changes: None
# Repository Changes: Documentation only.
# Safe to Re-run: No. Existing canonical artifact causes a guarded stop.
# ==============================================================================

set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.6-$STAMP"

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

[[ ! -e docs/governance/DOCUMENTATION_STANDARD.md ]] || \
  die "Refusing to overwrite existing Documentation Standard"

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

cat <<'ATLAS_M021_6_DOCUMENTATION_STANDARD_EOF' > docs/governance/DOCUMENTATION_STANDARD.md
# Atlas Documentation Standard

## Purpose

This document defines the canonical documentation requirements for Project Atlas.

Documentation is a first-class engineering artifact. It records what Atlas is,
how it behaves, why decisions were made, how operators use it, and what future
work must preserve.

## Documentation Philosophy

Atlas documentation should be accurate, current, discoverable, concise where
possible, complete where necessary, written for the intended audience, and
maintained with the implementation.

Documentation must describe supported behavior, not aspirational behavior
presented as complete. No public behavior should exist without an appropriate
documentation surface.

## Repository as the Source of Truth

The Git repository is the authoritative location for durable Atlas
documentation.

Conversations are engineering sessions. Decisions, contracts, procedures,
standards, and release records must be captured in repository-owned artifacts
when they are intended to outlive the session.

Documentation stored outside the repository may support development, but it is
not authoritative until incorporated into the repository.

## Documentation Categories

Primary categories include:

- roadmap and planning;
- changelog;
- build history;
- engineering specifications;
- architecture documentation;
- API documentation;
- CLI documentation;
- operational documentation;
- governance;
- ADRs and EDRs;
- release certification;
- user-facing documentation.

Each category has a distinct responsibility and should not duplicate unrelated
content unnecessarily.

## Required Repository Documents

The following documents are permanent project records:

```text
ROADMAP.md
CHANGELOG.md
docs/BUILD_LOG.md
docs/ENGINEERING_GUIDE.md
docs/ENGINEERING_CHECKLIST.md
docs/governance/
docs/specifications/
docs/architecture/
docs/api/
docs/cli/
docs/releases/
```

## Roadmap Requirements

`ROADMAP.md` defines planned, active, deferred, and completed milestone work.

Update it when milestone scope changes, a capability becomes required, an item
is completed, work is deferred, a release gate changes, or a new milestone is
introduced.

Roadmap status must match repository reality.

## Changelog Requirements

`CHANGELOG.md` records notable changes.

Add entries for new supported capability, changed public behavior,
compatibility changes, important documentation additions, fixes with user or
operator impact, deprecations, removals, and release-relevant engineering work.

Do not use the Changelog as a chronological build diary.

## Build Log Requirements

`docs/BUILD_LOG.md` records chronological implementation history.

A build-log entry should include applicable date, milestone or sprint,
objective, completed work, validation, limitations, and follow-up work.

The Build Log may contain more implementation detail than the Changelog.

## Engineering Specifications

Engineering specifications live under `docs/specifications/`.

A specification should define purpose, background, scope, exclusions,
repository impact, deliverables, validation, success criteria, risks, future
expansion, and references.

Specifications define approved intent before implementation. Material
deviations should be documented explicitly.

## Architecture Documentation

Architecture documentation lives under `docs/architecture/`.

It is required when work affects subsystem boundaries, package structure,
providers, services, public models, data flow, persistence, authentication,
authorization, cross-domain interaction, deployment topology, safety
boundaries, or compatibility architecture.

Architecture documentation should explain responsibilities, dependencies,
boundaries, public contracts, data flow, failure handling, constraints,
limitations, and extension points.

## API Documentation

API documentation lives under `docs/api/`.

It is required for supported Python, HTTP, event, or other programmatic
interfaces.

Document applicable public imports, classes, functions, methods, arguments,
returns, errors, serialized fields, JSON contracts, compatibility paths,
examples, and safety boundaries.

API documentation must match the canonical domain contract.

## CLI Documentation

CLI documentation lives under `docs/cli/`.

It should include usage, commands, positional arguments, options,
human-readable behavior, JSON behavior, output fields, errors, exit behavior,
examples, mutation boundaries, and compatibility notes.

Help text and CLI documentation must remain synchronized.

## Operational Documentation

Operational documentation should explain how to deploy, configure, validate,
maintain, recover, and troubleshoot Atlas.

Applicable topics include installation, configuration, storage, backups,
restore, updates, scheduling, diagnostics, logging, permissions, networking,
recovery, and maintenance procedures.

Potentially destructive commands must include safeguards and clear warnings.

## Governance Documentation

Governance documents live under `docs/governance/`.

Governance changes should be deliberate, reviewed against existing practice,
cross-linked from the governance index, recorded in the Build Log, recorded in
the Changelog when notable, and reflected in the Roadmap while active.

## ADR and EDR Documentation

Architecture Decision Records document significant architectural choices.
Engineering Decision Records may document significant implementation or
operational choices that do not require an ADR.

A decision record should include context, decision, rationale, alternatives,
consequences, status, and related work.

Do not create a decision record for trivial implementation detail.

## Release Documentation

Release documentation lives under `docs/releases/`.

It may include certification, release notes, known limitations, migration
notes, compatibility guarantees, validation summaries, support boundaries, and
approval status.

Certification summarizes validated evidence and does not replace testing,
runtime validation, audits, or implementation records.

## User-Facing Documentation

User-facing documentation should prioritize clarity and task completion.

It should be written for its audience: friends and family, administrators,
operators, developers, or contributors.

Terms should remain consistent across the Portal, CLI, help text, and docs.

## Documentation Structure

Documents should use clear heading levels and stable section organization.

Prefer descriptive headings, short paragraphs, focused lists, nearby examples,
relative links, and fenced code blocks with appropriate language identifiers.

Avoid duplicate sections, stale copied text, excessive prose, links to temporary
files, undocumented acronyms, and unexplained placeholders.

## Markdown Standards

Markdown should:

- use one H1 heading per document;
- use headings in logical order;
- use fenced code blocks for multiline examples;
- specify a code language when appropriate;
- use repository-relative links;
- end with a newline;
- avoid trailing whitespace;
- avoid broken local links.

## Examples and Commands

Examples must represent supported behavior.

Commands should use valid paths, preserve required quoting, include necessary
environment context, avoid secrets, use safe defaults, and state expected
results when useful.

Large file replacements should use guarded heredocs with unique terminators
when appropriate.

Examples must not depend silently on prior conversation context.

## Compatibility Documentation

Compatibility documentation is required when preserving or changing public
imports, module paths, command names, serialized fields, configuration formats,
storage layouts, provider behavior, or migration paths.

Document canonical behavior, supported legacy behavior, migration requirements,
deprecation status, and planned removal conditions.

Compatibility claims must be tested.

## Safety Documentation

Documentation for mutating operations should identify authorization
requirements, backup expectations, prerequisites, affected services,
validation, rollback or recovery, and irreversible consequences.

Read-only and mutating behavior must be clearly distinguished.

Never include credentials, tokens, private keys, or sensitive personal data.

## Cross-Linking

Documentation should link related authoritative documents.

Cross-links should reduce duplication rather than create circular navigation
without clear ownership.

## Documentation Updates During a Sprint

Documentation should be updated during implementation.

Before commit, review whether the change requires updates to:

```text
ROADMAP.md
CHANGELOG.md
docs/BUILD_LOG.md
docs/architecture/
docs/api/
docs/cli/
docs/governance/
docs/specifications/
docs/releases/
```

Not every sprint requires every document. The documentation decision should be
proportional to the changed public or engineering surface.

## Documentation Validation

Validate applicable required files, headings, local links, governance indexes,
registered commands, public exports, CLI help, living-document markers,
Markdown formatting, and `git diff --check`.

Untracked documentation must be reviewed directly because normal `git diff`
does not display it.

## Documentation Review

Review should confirm that documentation matches implementation, scope matches
the approved sprint, terminology is consistent, safety boundaries are clear,
compatibility behavior is accurate, limitations are documented, links resolve,
examples are usable, and ownership is unambiguous.

Documentation review is an engineering review, not only proofreading.

## Documentation Lifecycle

Documentation may be active, superseded, deprecated, or archived.

Superseded documents should identify their replacement when retained.

Temporary exports, review bundles, and generated snapshots must follow the
repository artifact lifecycle and must not be mistaken for permanent
documentation.

## Definition of Documentation Complete

Documentation is complete only when every applicable condition is satisfied:

- public behavior is documented;
- architecture changes are documented;
- API and CLI references are updated;
- operational impact is documented;
- compatibility and safety boundaries are documented;
- Build Log, Changelog, and Roadmap are updated as required;
- governance indexes and cross-links are current;
- local links resolve;
- examples are valid;
- repository validation passes;
- documentation is reviewed before commit.

Implemented but undocumented work is not complete Atlas work.
ATLAS_M021_6_DOCUMENTATION_STANDARD_EOF

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
old = "- [ ] `DOCUMENTATION_STANDARD.md`"
new = "- [x] [`DOCUMENTATION_STANDARD.md`](DOCUMENTATION_STANDARD.md)"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("Governance Documentation Standard entry not found")
path.write_text(text)

append_once(
    "docs/ENGINEERING_GUIDE.md",
    "## Documentation Standard",
    '''
## Documentation Standard

The canonical Atlas documentation requirements are defined in
[`governance/DOCUMENTATION_STANDARD.md`](governance/DOCUMENTATION_STANDARD.md).
''',
)

append_once(
    "docs/ENGINEERING_CHECKLIST.md",
    "## Documentation Standard Review",
    '''
## Documentation Standard Review

- [ ] Public behavior and architecture are documented where applicable.
- [ ] API, CLI, operational, compatibility, and safety documentation are current.
- [ ] Build Log, Changelog, and Roadmap updates are complete where required.
- [ ] Local links, examples, and repository formatting validate successfully.
''',
)

append_once(
    "docs/BUILD_LOG.md",
    "## M-021.6 — Documentation Standard",
    '''
---

# 2026-08-02

## M-021.6 — Documentation Standard

### Completed

- Added the permanent Atlas Documentation Standard.
- Formalized architecture, API, CLI, operational, governance, decision-record,
  release, user-facing, compatibility, and safety documentation requirements.
- Formalized Roadmap, Changelog, and Build Log responsibilities.
- Linked the standard from governance and engineering documentation.
- Added documentation review gates to the Engineering Checklist.
- Marked the Documentation Standard complete in the Roadmap.

### Validation

- Required-section validation.
- Local Markdown-link validation.
- Living-document marker validation.
- `git diff --check`.
''',
)

path = Path("CHANGELOG.md")
text = path.read_text()
entry = (
    "- Added the Atlas Documentation Standard governance document defining "
    "architecture, API, CLI, operational, governance, release, and living-"
    "document requirements.\n"
)
if entry not in text:
    anchor = "### Documentation\n\n"
    if anchor not in text:
        raise SystemExit("CHANGELOG Documentation anchor not found")
    path.write_text(text.replace(anchor, anchor + entry, 1))

path = Path("ROADMAP.md")
text = path.read_text()
old = "- [ ] Documentation Standard"
new = "- [x] Documentation Standard"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("ROADMAP Documentation Standard entry not found")
path.write_text(text)
PY

PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

"$PYTHON" - <<'PY'
from pathlib import Path
import re

artifact = Path("docs/governance/DOCUMENTATION_STANDARD.md")
text = artifact.read_text()

required = (
    "# Atlas Documentation Standard",
    "## Documentation Philosophy",
    "## Repository as the Source of Truth",
    "## Required Repository Documents",
    "## Roadmap Requirements",
    "## Changelog Requirements",
    "## Build Log Requirements",
    "## Engineering Specifications",
    "## Architecture Documentation",
    "## API Documentation",
    "## CLI Documentation",
    "## Operational Documentation",
    "## Governance Documentation",
    "## ADR and EDR Documentation",
    "## Release Documentation",
    "## Documentation Validation",
    "## Documentation Review",
    "## Definition of Documentation Complete",
)
for heading in required:
    if heading not in text:
        raise SystemExit(f"Missing Documentation Standard heading: {heading}")

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
        if local and not (document.parent / local).resolve().exists():
            failures.append(f"{document}: broken link -> {target}")

if failures:
    raise SystemExit("\n".join(failures))

print("M-021.6 Documentation Standard validated.")
PY

git diff --check

printf '\nM-021.6 Documentation Standard applied successfully.\n'
printf 'Backup: %s\n' "$BACKUP_DIR"
printf '\nReview with:\n'
printf '  sed -n "1,460p" docs/governance/DOCUMENTATION_STANDARD.md\n'
printf '  git status --short\n'
printf '  git diff --check\n'
printf '  git diff --stat\n'
