#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.8-$STAMP"

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

[[ ! -e docs/governance/VERSIONING_AND_CONTRIBUTING.md ]] || \
  die "Refusing to overwrite existing Versioning and Contributing Standard"

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

cat <<'ATLAS_M021_8_VERSIONING_AND_CONTRIBUTING_EOF' > docs/governance/VERSIONING_AND_CONTRIBUTING.md
# Atlas Versioning and Contributing Standard

## Purpose

This document defines the canonical versioning, branching, commit, review, and
contribution requirements for Project Atlas.

Its goal is to help Atlas evolve predictably without sacrificing stability,
compatibility, repository clarity, or maintainability.

## Versioning Philosophy

Atlas uses version numbers to communicate compatibility and release intent.

Version changes should reflect meaningful user, operator, developer, or
compatibility impact. Version numbers are not changed for appearance, trend,
marketing pressure, or novelty.

Atlas prioritizes:

- stability;
- reliability;
- compatibility;
- maintainability;
- operational clarity;
- user value.

## Semantic Versioning

Atlas follows Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

### Major Version

Increment the major version when a release introduces intentional incompatible
changes to supported public behavior.

Examples include:

- removal of supported public APIs;
- incompatible serialized contract changes;
- incompatible configuration changes;
- unsupported storage-layout migrations;
- removal of compatibility paths;
- major deployment-model changes.

Major releases require explicit migration documentation and release
certification.

### Minor Version

Increment the minor version when a release adds backward-compatible capability.

Examples include:

- new commands;
- new API endpoints;
- new optional modules;
- new domain services;
- new reports or fields that preserve existing contracts;
- new administrative or user-facing features.

Minor releases should preserve supported existing behavior.

### Patch Version

Increment the patch version for backward-compatible corrections.

Examples include:

- bug fixes;
- documentation corrections tied to released behavior;
- performance improvements without contract changes;
- compatibility fixes;
- operational reliability improvements;
- security fixes that preserve supported interfaces.

## Pre-Release Versions

Pre-release identifiers may be used for release candidates:

```text
1.0.0-rc.1
1.0.0-rc.2
```

Pre-release builds are not final releases.

They may receive fixes before certification, but should not introduce unrelated
scope after the release candidate boundary is established.

## Version Sources

The canonical version source must remain explicit and consistent across the
repository.

Applicable locations may include:

- `VERSION`;
- package metadata;
- CLI version output;
- release documentation;
- Git tags.

Version-bearing files must be updated together when required.

## Release Types

Atlas recognizes these release types:

- development snapshot;
- release candidate;
- patch release;
- minor release;
- major release;
- emergency maintenance release.

Every release type remains subject to applicable testing, documentation,
repository, and certification requirements.

## Branch Strategy

The default branch is the stable integration branch.

Feature work should occur on focused branches.

Recommended branch names include:

```text
feature/<short-description>
fix/<short-description>
docs/<short-description>
refactor/<short-description>
release/<version>
```

Existing long-running branches may continue when they represent an intentional
milestone integration surface.

Branch names should be concise and descriptive.

## Branch Requirements

A working branch should:

- have one primary objective whenever practical;
- remain synchronized with its intended base;
- avoid unrelated changes;
- preserve a reviewable history;
- pass applicable validation before merge;
- document intentional compatibility impact.

Do not mix unrelated milestones merely to reduce the number of branches.

## Sprint Workflow

A contribution should follow the Atlas Development Workflow:

```text
Repository Review
↓
Architecture Review
↓
Specification and Scope Approval
↓
Implementation
↓
Focused Validation
↓
Regression Validation
↓
Runtime Validation
↓
Documentation
↓
Repository Review
↓
Commit
↓
Push
```

Not every sprint requires every validation layer, but every omission should be
appropriate to the changed surface.

## Contribution Philosophy

Contributions are evaluated by their fit with the whole Atlas environment.

A proposed change should clearly improve one or more of:

- stability;
- reliability;
- maintainability;
- operational simplicity;
- user experience;
- compatibility;
- repository clarity.

A change should not be accepted solely because:

- a framework is newer;
- a dependency is popular;
- another project uses it;
- it is more fashionable;
- it reduces lines while increasing complexity;
- it demonstrates novelty without practical benefit.

## Contribution Requirements

Every contribution should include applicable:

- approved scope;
- implementation;
- tests;
- runtime validation;
- documentation;
- compatibility analysis;
- migration notes;
- repository review;
- clear commit history.

Contributors should not assume conversation history is available to reviewers.

The repository contribution must be understandable on its own.

## Commit Message Convention

Atlas uses concise, imperative, structured commit messages.

Preferred form:

```text
type(scope): summary
```

Common types include:

- `feat`
- `fix`
- `docs`
- `test`
- `refactor`
- `chore`
- `build`
- `ci`
- `perf`
- `revert`

Examples:

```text
feat(service-lifecycle): add maintenance history
fix(service-lifecycle): preserve digest-only image references
docs(governance): add Testing Standard
test(identity): cover invitation expiration
```

The summary should:

- describe the completed change;
- remain concise;
- avoid ending punctuation;
- avoid vague wording;
- identify the affected domain when useful.

## Commit Scope

Each commit should have one primary objective whenever practical.

A commit should not combine:

- unrelated features;
- cleanup unrelated to the active sprint;
- broad formatting changes;
- generated artifacts not intended for the repository;
- temporary review files;
- unrelated documentation rewrites.

Small corrective commits are acceptable when they preserve an honest pushed
history.

## Staging Requirements

Stage intended files explicitly when practical.

Before staging:

```text
git status --short
git diff --check
git diff --stat
git diff
```

After staging:

```text
git diff --cached --check
git diff --cached --stat
git diff --cached
```

Placeholders such as `git add ...` must not be presented as literal commands.

## Review Expectations

Review should confirm:

- scope matches the approved sprint;
- the change benefits Atlas as a whole;
- stability is not weakened without explicit justification;
- public contracts are preserved or migration is documented;
- tests cover changed behavior;
- documentation matches implementation;
- repository artifacts have an appropriate lifecycle;
- `git diff --check` passes;
- staged content matches the intended commit.

## Pull Requests

When pull requests are used, they should include:

- objective;
- summary of changes;
- validation performed;
- compatibility impact;
- documentation updates;
- known limitations;
- related specification or ADR;
- release impact.

Pull requests should remain focused and reviewable.

## Merge Requirements

A change may be merged only when every applicable gate passes:

- scope approval;
- implementation review;
- focused tests;
- regression tests;
- runtime validation;
- documentation review;
- compatibility review;
- repository review;
- clean staged diff;
- required approval.

Known failures must not be silently ignored.

## Compatibility Expectations

Backward compatibility should be preserved whenever practical.

Compatibility includes:

- public imports;
- CLI commands;
- JSON fields;
- configuration formats;
- storage layouts;
- provider defaults;
- documented operational behavior.

Breaking changes require:

- explicit design review;
- ADR coverage where architectural;
- migration documentation;
- major-version evaluation;
- release certification.

## Deprecation Policy

Deprecation should be deliberate and documented.

A deprecation should identify:

- deprecated behavior;
- replacement;
- reason;
- compatibility period;
- migration path;
- planned removal condition;
- affected version.

Deprecated behavior should remain tested while supported.

Removal should not occur until the replacement is validated and the release
policy permits it.

## Dependency Changes

Dependency updates should be made for a clear reason.

Acceptable reasons include:

- security;
- compatibility;
- bug fixes;
- required capability;
- supported platform changes;
- maintenance sustainability.

Do not update dependencies merely to remain current.

Major dependency changes require compatibility and operational review.

## Reverts

A revert is appropriate when a change threatens stability, compatibility,
security, or release readiness.

Reverts should:

- preserve the original commit history;
- state what is being reverted;
- explain why;
- identify follow-up work;
- include validation.

## Emergency Changes

Emergency maintenance changes may use an abbreviated planning cycle, but they
still require:

- clear scope;
- risk assessment;
- focused validation;
- repository review;
- documentation after stabilization;
- follow-up regression when applicable.

Urgency does not remove the need for accountability.

## External Contributions

External contributions must follow the same engineering standards as internal
work.

No contributor is required to know undocumented project history.

Contribution instructions should provide enough repository context to complete
supported work safely.

## Security and Sensitive Data

Contributions must not include:

- credentials;
- tokens;
- private keys;
- private service URLs;
- sensitive personal information;
- production secrets;
- unauthorized copyrighted content.

Sensitive values discovered in history should be treated as a security issue.

## Tooling and Generated Artifacts

Tooling committed to the repository should provide lasting engineering or
operational value.

Temporary generators, review bundles, caches, and snapshots should not be
committed unless their retention is explicitly justified.

Apply scripts should follow the documented tooling lifecycle.

## Release Impact Review

Before merge, determine whether the change affects:

- patch version;
- minor version;
- major version;
- release notes;
- migration notes;
- certification;
- compatibility guarantees.

Not every commit requires a release, but every release-relevant change should be
classified correctly.

## Validation Requirements

Versioning and contribution validation should include applicable:

- branch review;
- commit-message review;
- focused tests;
- regression tests;
- runtime validation;
- documentation validation;
- compatibility validation;
- staged-diff review;
- `git diff --check`.

## Definition of Contribution Complete

A contribution is complete only when every applicable condition is satisfied:

- scope is approved;
- implementation is complete;
- validation passes;
- compatibility is preserved or documented;
- documentation is complete;
- release impact is assessed;
- repository review passes;
- commit history is clear;
- changes are pushed;
- the working tree is clean.

Code or documentation that exists only locally is not a completed Atlas
contribution.
ATLAS_M021_8_VERSIONING_AND_CONTRIBUTING_EOF

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

replacements = (
    (
        "- [ ] `VERSIONING.md`",
        "- [x] [`VERSIONING_AND_CONTRIBUTING.md`](VERSIONING_AND_CONTRIBUTING.md)",
    ),
    (
        "- [ ] `CONTRIBUTING.md`",
        None,
    ),
)

old_versioning, new_versioning = replacements[0]
if old_versioning in text:
    text = text.replace(old_versioning, new_versioning, 1)
elif new_versioning not in text:
    raise SystemExit("Governance versioning entry not found")

old_contributing, _ = replacements[1]
if old_contributing in text:
    text = text.replace(old_contributing + "\n", "", 1)

path.write_text(text)

append_once(
    "docs/ENGINEERING_GUIDE.md",
    "## Versioning and Contributing",
    """
## Versioning and Contributing

The canonical Atlas versioning, branching, commit, review, compatibility,
deprecation, and contribution requirements are defined in
[`governance/VERSIONING_AND_CONTRIBUTING.md`](governance/VERSIONING_AND_CONTRIBUTING.md).
""",
)

append_once(
    "docs/ENGINEERING_CHECKLIST.md",
    "## Versioning and Contribution Review",
    """
## Versioning and Contribution Review

- [ ] The branch and commit scope have one primary objective.
- [ ] Commit messages follow the Atlas convention.
- [ ] Compatibility, deprecation, and release impact were reviewed.
- [ ] Staged changes pass repository validation before commit.
""",
)

append_once(
    "docs/BUILD_LOG.md",
    "## M-021.8 — Versioning and Contributing",
    """
---

# 2026-08-02

## M-021.8 — Versioning and Contributing

### Completed

- Added the permanent Atlas Versioning and Contributing Standard.
- Formalized Semantic Versioning, release types, branch strategy, commit
  conventions, staging, review, merge, compatibility, deprecation, dependency,
  revert, emergency, security, and release-impact requirements.
- Linked the standard from governance and engineering documentation.
- Added contribution review gates to the Engineering Checklist.
- Marked Versioning and Contributing guidance complete in the Roadmap.

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
    "- Added the Atlas Versioning and Contributing Standard defining semantic "
    "versioning, branches, commits, review, compatibility, deprecation, and "
    "merge requirements.\n"
)
if entry not in text:
    anchor = "### Documentation\n\n"
    if anchor not in text:
        raise SystemExit("CHANGELOG Documentation anchor not found")
    path.write_text(text.replace(anchor, anchor + entry, 1))

path = Path("ROADMAP.md")
text = path.read_text()
old = "- [ ] Versioning and Contributing guidance"
new = "- [x] Versioning and Contributing guidance"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("ROADMAP Versioning entry not found")
path.write_text(text)
PY

PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

"$PYTHON" - <<'PY'
from pathlib import Path
import re

artifact = Path("docs/governance/VERSIONING_AND_CONTRIBUTING.md")
text = artifact.read_text()

required = (
    "# Atlas Versioning and Contributing Standard",
    "## Versioning Philosophy",
    "## Semantic Versioning",
    "## Pre-Release Versions",
    "## Branch Strategy",
    "## Sprint Workflow",
    "## Contribution Philosophy",
    "## Commit Message Convention",
    "## Staging Requirements",
    "## Review Expectations",
    "## Merge Requirements",
    "## Compatibility Expectations",
    "## Deprecation Policy",
    "## Dependency Changes",
    "## Emergency Changes",
    "## Validation Requirements",
    "## Definition of Contribution Complete",
)

for heading in required:
    if heading not in text:
        raise SystemExit(f"Missing Versioning and Contributing heading: {heading}")

documents = (
    artifact,
    Path("docs/governance/README.md"),
    Path("docs/ENGINEERING_GUIDE.md"),
    Path("docs/ENGINEERING_CHECKLIST.md"),
    Path("docs/BUILD_LOG.md"),
    Path("CHANGELOG.md"),
    Path("ROADMAP.md"),
)

pattern = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
failures = []

for document in documents:
    for target in pattern.findall(document.read_text()):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        local = target.split("#", 1)[0]
        if local and not (document.parent / local).resolve().exists():
            failures.append(f"{document}: broken link -> {target}")

if failures:
    raise SystemExit("\n".join(failures))

markers = {
    "docs/governance/README.md": "VERSIONING_AND_CONTRIBUTING.md",
    "docs/ENGINEERING_GUIDE.md": "## Versioning and Contributing",
    "docs/ENGINEERING_CHECKLIST.md": "## Versioning and Contribution Review",
    "docs/BUILD_LOG.md": "## M-021.8 — Versioning and Contributing",
    "CHANGELOG.md": "Atlas Versioning and Contributing Standard",
    "ROADMAP.md": "- [x] Versioning and Contributing guidance",
}

for path_value, marker in markers.items():
    if marker not in Path(path_value).read_text():
        raise SystemExit(f"{path_value} is missing marker: {marker}")

print("M-021.8 Versioning and Contributing validated.")
PY

git diff --check

printf '\nM-021.8 Versioning and Contributing applied successfully.\n'
printf 'Backup: %s\n' "$BACKUP_DIR"
printf '\nReview with:\n'
printf '  sed -n "1,420p" docs/governance/VERSIONING_AND_CONTRIBUTING.md\n'
printf '  git status --short\n'
printf '  git diff --check\n'
printf '  git diff --stat\n'
