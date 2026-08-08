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
