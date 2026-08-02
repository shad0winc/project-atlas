#!/usr/bin/env bash
#
# Project Atlas — M-021.9 Release Policy
set -Eeuo pipefail

ROOT="${1:-/opt/project-atlas}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="$ROOT/.atlas-backups/m021.9-$STAMP"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

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

[[ ! -e docs/governance/RELEASE_POLICY.md ]] || \
  die "Refusing to overwrite existing Release Policy"

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

cat <<'ATLAS_M021_9_RELEASE_POLICY_EOF' > docs/governance/RELEASE_POLICY.md
# Atlas Release Policy

## Purpose

This document defines the canonical release-readiness, certification, approval,
publication, maintenance, rollback, and end-of-life policy for Project Atlas.

A release is not merely a version number or a tagged commit. It is a validated
statement that the repository, runtime behavior, documentation, compatibility,
and operational boundaries are ready for supported use.

## Release Philosophy

Atlas ships when it satisfies its engineering standards—not because a calendar
date arrives.

Release decisions prioritize:

- stability;
- reliability;
- compatibility;
- maintainability;
- operational clarity;
- security;
- user and administrator experience.

Schedule pressure, novelty, popularity, or incomplete feature demand are not
sufficient reasons to lower release standards.

## Release Authority

A release may be approved only when all mandatory engineering gates have passed.

Release authority belongs to the project owner or explicitly authorized
maintainers.

Approval should be based on evidence recorded in the repository.

A release is not approved solely because:

- a milestone date arrived;
- a feature is highly requested;
- work has been in progress for a long time;
- later fixes are assumed to be easy;
- another project released similar functionality;
- the release would improve perceived momentum.

## Supported Release Types

Atlas recognizes the following release types:

- development snapshot;
- release candidate;
- patch release;
- minor release;
- major release;
- emergency maintenance release.

Each type has different scope expectations but remains subject to applicable
validation, documentation, compatibility, and repository review.

## Development Snapshots

Development snapshots represent in-progress work.

They:

- are not certified releases;
- may contain incomplete capability;
- may change before release;
- must not be presented as production-ready;
- should not establish unsupported compatibility guarantees.

Development snapshots may be used for controlled testing and review.

## Release Candidates

A release candidate represents a feature-complete release boundary awaiting
final validation and certification.

A release candidate should:

- contain the intended release scope;
- avoid unrelated new features;
- receive only fixes, documentation corrections, compatibility repairs, and
  release-blocking improvements;
- pass the full required validation suite;
- document known limitations.

Release candidates may use identifiers such as:

```text
1.0.0-rc.1
1.0.0-rc.2
```

A later release candidate supersedes the earlier candidate for release review.

## Patch Releases

Patch releases contain backward-compatible corrections.

Appropriate scope includes:

- bug fixes;
- security fixes that preserve supported contracts;
- compatibility repairs;
- reliability improvements;
- documentation corrections tied to released behavior;
- low-risk performance improvements.

Patch releases should remain narrow.

Unrelated features should be deferred to a minor release.

## Minor Releases

Minor releases add backward-compatible capability.

Appropriate scope includes:

- new commands;
- new API endpoints;
- new optional modules;
- new domain services;
- new user or administrator features;
- additive serialized fields that preserve existing contracts;
- expanded supported integrations.

Minor releases must preserve documented compatibility unless an exception is
explicitly approved and versioning is reconsidered.

## Major Releases

Major releases may introduce intentional incompatible changes.

Examples include:

- removal of supported public APIs;
- incompatible configuration changes;
- incompatible serialized-contract changes;
- removal of compatibility aliases;
- unsupported storage-layout changes;
- major deployment-topology changes;
- replacement of a supported workflow without compatibility.

Major releases require:

- ADR coverage when architectural;
- migration documentation;
- compatibility review;
- rollback or recovery planning;
- release certification;
- explicit approval.

## Emergency Maintenance Releases

Emergency maintenance releases address urgent security, availability,
corruption, or critical compatibility issues.

They may use an abbreviated planning cycle, but they still require:

- clear scope;
- risk assessment;
- focused validation;
- repository review;
- release documentation;
- follow-up regression when immediate full validation is impractical;
- explicit approval.

Urgency does not eliminate accountability.

## Semantic Version Alignment

Release classification must align with the Atlas Versioning and Contributing
Standard.

Use:

```text
MAJOR.MINOR.PATCH
```

Version impact should reflect supported public behavior, not the number of files
changed.

The canonical version must remain consistent across applicable:

- `VERSION`;
- package metadata;
- CLI version output;
- release documentation;
- Git tags.

## Release Scope

Every release must have a defined scope.

The scope should identify:

- included milestones;
- included fixes;
- supported capabilities;
- deferred work;
- known limitations;
- compatibility impact;
- migration impact;
- release type.

Scope should be frozen at the release-candidate boundary except for genuine
release blockers, defects, compatibility repairs, security issues, and required
documentation corrections.

## Release Readiness Gates

A release is eligible for certification only after every applicable gate passes.

Required gates include:

- scope complete;
- implementation complete;
- focused validation complete;
- regression validation complete;
- runtime validation complete where applicable;
- compatibility review complete;
- migration requirements complete;
- security review complete;
- documentation complete;
- repository review complete;
- release artifacts reviewed;
- known limitations documented;
- required approvals recorded.

## Implementation Gate

The implementation gate confirms:

- approved scope is present;
- incomplete features are not presented as supported;
- deferred work is recorded;
- feature flags or optional modules behave as documented;
- public contracts match implementation;
- temporary development behavior is removed or explicitly documented.

## Testing Gate

The testing gate follows the Atlas Testing Standard.

Applicable evidence includes:

- focused unit tests;
- model tests;
- service tests;
- provider tests;
- CLI contract tests;
- compatibility tests;
- integration tests;
- full regression tests;
- subtests;
- release-specific validation.

A required failing test blocks release certification.

## Runtime Validation Gate

Runtime validation confirms supported behavior in the real Atlas environment.

Applicable validation may include:

```text
atlas verify
atlas doctor
atlas health
atlas service list
atlas service doctor
atlas service updates
atlas service history
atlas modules verify
```

Runtime checks should:

- use supported commands;
- parse JSON when machine-readable output is provided;
- validate representative real services;
- preserve read-only and mutation boundaries;
- avoid destructive operations unless explicitly authorized;
- record significant results.

A successful automated suite does not replace runtime validation when runtime
behavior is part of the release scope.

## Public Contract Gate

The public-contract gate verifies applicable:

- package exports;
- model serialization;
- JSON schemas;
- CLI help and command registration;
- API documentation;
- compatibility aliases;
- provider interfaces;
- service return contracts;
- error behavior;
- timestamp format.

Public contracts should be deterministic and documented.

## Compatibility Gate

Compatibility review must consider:

- public imports;
- module paths;
- CLI commands;
- CLI options;
- JSON fields;
- configuration formats;
- storage layouts;
- provider defaults;
- documented operational behavior;
- supported migration paths.

Any intentional incompatibility must be:

- classified correctly under Semantic Versioning;
- documented;
- approved;
- included in migration guidance;
- reflected in release notes and certification.

## Migration Gate

When migration is required, documentation must define:

- prerequisites;
- backup expectations;
- ordered steps;
- affected files or services;
- expected downtime;
- validation;
- rollback or recovery;
- irreversible effects;
- supported source versions;
- target version.

Migration instructions should be reproducible and tested where practical.

## Security Gate

Security review should verify applicable:

- no credentials or secrets are committed;
- authentication and authorization behavior is documented;
- sensitive output is not exposed;
- dependencies do not introduce known unacceptable risk;
- permissions follow least privilege where practical;
- mutation paths require appropriate authorization;
- user data and operational metadata are handled safely;
- release artifacts do not include private review material.

Known security issues that materially affect supported use block release unless
the risk is explicitly accepted and documented.

## Performance Gate

Performance review is required when a release materially changes:

- startup behavior;
- API latency;
- CLI response time;
- database or storage behavior;
- background scheduling;
- media scanning;
- provider calls;
- memory usage;
- CPU usage;
- network usage.

Performance review should be proportionate to risk.

Atlas does not require artificial benchmarks for changes with no meaningful
performance surface.

## Documentation Gate

Release documentation must satisfy the Atlas Documentation Standard.

Applicable updates include:

- `CHANGELOG.md`;
- `ROADMAP.md`;
- `docs/BUILD_LOG.md`;
- architecture documentation;
- API documentation;
- CLI documentation;
- operational documentation;
- migration notes;
- known limitations;
- release notes;
- release certification;
- governance references.

Documentation must describe actual supported behavior.

## Repository Gate

Before certification, review:

```text
git status --short
git diff --check
git diff --stat
git diff
```

Before the release commit, also review:

```text
git diff --cached --check
git diff --cached --stat
git diff --cached
```

The release branch should have:

- no unexplained untracked files;
- no temporary caches;
- no unintended review bundles;
- no unresolved merge conflicts;
- no trailing-whitespace violations;
- no unrelated staged changes;
- a clean working tree after the release commit.

## Release Audit

Subsystems or major releases may require a formal release audit.

An audit may include:

- Python compilation;
- shell syntax validation;
- public API validation;
- documentation validation;
- compatibility validation;
- full regression;
- runtime human-output smoke tests;
- runtime JSON contract validation;
- repository hygiene review;
- permanent audit report;
- review bundle.

Temporary audit evidence should follow the repository artifact lifecycle.

The permanent release record should summarize evidence without requiring
temporary artifacts to remain in the repository.

## Release Certification

Release certification is the permanent statement that required release gates
passed.

Certification should identify:

- release version;
- release type;
- branch;
- commit;
- date;
- included milestones;
- validation performed;
- test totals where relevant;
- runtime checks;
- compatibility status;
- migration status;
- known limitations;
- rollback expectations;
- approval status.

Certification must not claim validation that was not performed.

## Known Limitations

Known limitations should be explicit.

A limitation may be accepted when it:

- does not violate the release's supported contract;
- has a safe workaround or bounded impact;
- is documented;
- does not threaten data integrity or security;
- is approved.

Unbounded, hidden, or release-blocking limitations must not be reclassified as
acceptable merely to ship.

## Rollback Expectations

Every release should have a rollback or recovery strategy where practical.

Rollback planning should consider:

- application version;
- configuration;
- database or state migrations;
- storage changes;
- service dependencies;
- Docker images;
- backups;
- user impact;
- downtime.

Not every change is fully reversible.

Irreversible changes require explicit warning, backup, validation, and recovery
planning.

## Release Approval

Release approval requires:

- certification complete;
- mandatory gates passed;
- known limitations accepted;
- version confirmed;
- release commit reviewed;
- release tag ready;
- publication artifacts ready;
- project-owner or authorized-maintainer approval.

Approval should be recorded in the release certification.

## Release Commit

The release commit should:

- contain only release-related changes;
- update version sources;
- update release notes and certification;
- preserve a clean staged diff;
- use a clear commit message;
- pass staged-diff validation.

Example:

```text
chore(release): certify Project Atlas v1.0.0
```

## Git Tags

Final releases should use signed or annotated tags when supported by the
repository workflow.

Recommended form:

```text
v1.0.0
v1.0.1
v1.1.0
```

Pre-release tags may use:

```text
v1.0.0-rc.1
```

Tags must point to the certified release commit.

## Publication

Publication may include:

- GitHub release;
- release notes;
- source archive;
- installation or update instructions;
- migration guidance;
- known limitations;
- checksums or signatures where applicable.

Only certified artifacts should be presented as final releases.

## Post-Release Validation

After publication, perform applicable:

- tag verification;
- version-output verification;
- installation validation;
- update-path validation;
- runtime smoke tests;
- documentation-link review;
- release-artifact review.

Post-release defects should be triaged against patch, emergency, or deferred
work policy.

## Maintenance Releases

Maintenance releases should:

- remain narrow;
- preserve compatibility;
- avoid unrelated features;
- include focused regression;
- update release documentation;
- receive explicit approval.

Maintenance work should favor stability over opportunistic refactoring.

## Supported Release Policy

The project should document which release lines are supported.

At minimum, documentation should clarify:

- current stable release;
- current release candidate;
- supported prior versions if any;
- security-fix eligibility;
- upgrade expectations;
- end-of-life status.

Support commitments should match available maintenance capacity.

## End-of-Life Policy

A release may reach end of life when:

- it is superseded by a supported release;
- dependencies no longer support it;
- security maintenance is impractical;
- compatibility would undermine current stability;
- the support period ends.

End-of-life documentation should include:

- affected versions;
- effective date;
- reason;
- recommended target version;
- migration guidance;
- remaining support exceptions, if any.

End of life must not be announced without a supported upgrade path when one is
reasonably possible.

## Release Failure Handling

If a release gate fails:

- stop certification;
- record the failure;
- determine whether it is in scope;
- fix or explicitly defer only when policy permits;
- rerun affected validation;
- update certification evidence.

Do not weaken valid tests, omit known failures, or redefine release criteria
after failure merely to obtain approval.

## Release Certification Checklist

### Scope

- [ ] Release type is identified.
- [ ] Version is correct.
- [ ] Included milestones are complete.
- [ ] Deferred work is documented.
- [ ] Known limitations are documented.

### Implementation

- [ ] Approved implementation is complete.
- [ ] Public contracts match implementation.
- [ ] Temporary development behavior is removed or documented.

### Validation

- [ ] Focused tests pass.
- [ ] Regression tests pass.
- [ ] Compatibility tests pass.
- [ ] Runtime validation passes where applicable.
- [ ] JSON contracts validate where applicable.
- [ ] Release audit passes when required.

### Documentation

- [ ] Changelog is current.
- [ ] Roadmap is current.
- [ ] Build Log is current.
- [ ] Architecture, API, CLI, and operational docs are current.
- [ ] Migration and known-limitations docs are complete.
- [ ] Release certification is complete.

### Repository

- [ ] `git diff --check` passes.
- [ ] Staged diff is reviewed.
- [ ] Version sources agree.
- [ ] Working tree is clean after commit.
- [ ] Release tag points to the certified commit.

### Approval

- [ ] Security review is complete.
- [ ] Compatibility review is complete.
- [ ] Rollback or recovery is documented.
- [ ] Required approval is recorded.
- [ ] Publication artifacts are ready.

## Definition of Release Complete

A release is complete only when every applicable condition is satisfied:

- scope is complete;
- required validation passes;
- runtime behavior is verified;
- public contracts are stable;
- compatibility and migration are documented;
- security and performance concerns are reviewed;
- release documentation is complete;
- certification is approved;
- release commit is pushed;
- release tag is created;
- publication is complete;
- post-release validation passes;
- repository state accurately reflects the released software.

Software that is feature-complete but uncertified, unpublished, or unsupported
by accurate repository documentation is not a complete Atlas release.
ATLAS_M021_9_RELEASE_POLICY_EOF

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
old = "- [ ] `RELEASE_POLICY.md`"
new = "- [x] [`RELEASE_POLICY.md`](RELEASE_POLICY.md)"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("Governance Release Policy entry not found")
path.write_text(text)

append_once(
    "docs/ENGINEERING_GUIDE.md",
    "## Release Policy",
    """
## Release Policy

The canonical Atlas release-readiness and certification requirements are
defined in [`governance/RELEASE_POLICY.md`](governance/RELEASE_POLICY.md).
""",
)

append_once(
    "docs/ENGINEERING_CHECKLIST.md",
    "## Release Policy Review",
    """
## Release Policy Review

- [ ] Release type, version, and scope are correct.
- [ ] Testing, runtime, compatibility, security, and documentation gates passed.
- [ ] Rollback or recovery and known limitations are documented.
- [ ] Certification, approval, publication, and repository checks are complete.
""",
)

append_once(
    "docs/BUILD_LOG.md",
    "## M-021.9 — Release Policy",
    """
---

# 2026-08-02

## M-021.9 — Release Policy

### Completed

- Added the permanent Atlas Release Policy.
- Formalized release types, readiness gates, validation, compatibility,
  migration, security, performance, rollback, certification, approval,
  publication, maintenance, support, and end-of-life requirements.
- Added a canonical release certification checklist.
- Linked the Release Policy from governance and engineering documentation.
- Added release review gates to the Engineering Checklist.
- Marked Release Policy complete in the Roadmap.

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
    "- Added the Atlas Release Policy defining release readiness, validation, "
    "certification, approval, publication, maintenance, and end-of-life "
    "requirements.\n"
)
if entry not in text:
    anchor = "### Documentation\n\n"
    if anchor not in text:
        raise SystemExit("CHANGELOG Documentation anchor not found")
    path.write_text(text.replace(anchor, anchor + entry, 1))

path = Path("ROADMAP.md")
text = path.read_text()
old = "- [ ] Release Policy"
new = "- [x] Release Policy"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("ROADMAP Release Policy entry not found")
path.write_text(text)
PY

PYTHON="$ROOT/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"

"$PYTHON" - <<'PY'
from pathlib import Path
import re

artifact = Path("docs/governance/RELEASE_POLICY.md")
text = artifact.read_text()

required = (
    "# Atlas Release Policy",
    "## Release Philosophy",
    "## Release Authority",
    "## Supported Release Types",
    "## Release Candidates",
    "## Semantic Version Alignment",
    "## Release Readiness Gates",
    "## Testing Gate",
    "## Runtime Validation Gate",
    "## Compatibility Gate",
    "## Migration Gate",
    "## Security Gate",
    "## Documentation Gate",
    "## Repository Gate",
    "## Release Audit",
    "## Release Certification",
    "## Rollback Expectations",
    "## Release Approval",
    "## Maintenance Releases",
    "## End-of-Life Policy",
    "## Release Certification Checklist",
    "## Definition of Release Complete",
)

for heading in required:
    if heading not in text:
        raise SystemExit(f"Missing Release Policy heading: {heading}")

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
    "docs/governance/README.md": "RELEASE_POLICY.md",
    "docs/ENGINEERING_GUIDE.md": "## Release Policy",
    "docs/ENGINEERING_CHECKLIST.md": "## Release Policy Review",
    "docs/BUILD_LOG.md": "## M-021.9 — Release Policy",
    "CHANGELOG.md": "Atlas Release Policy",
    "ROADMAP.md": "- [x] Release Policy",
}

for path_value, marker in markers.items():
    if marker not in Path(path_value).read_text():
        raise SystemExit(f"{path_value} is missing marker: {marker}")

print("M-021.9 Release Policy validated.")
PY

git diff --check

printf '\nM-021.9 Release Policy applied successfully.\n'
printf 'Backup: %s\n' "$BACKUP_DIR"
printf '\nReview with:\n'
printf '  sed -n "1,760p" docs/governance/RELEASE_POLICY.md\n'
printf '  git status --short\n'
printf '  git diff --check\n'
printf '  git diff --stat\n'
