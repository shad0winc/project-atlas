# Project Atlas Engineering Guide

## Purpose

This guide defines how Project Atlas is designed, implemented, validated,
documented, and released. The repository is the source of truth, and each
development session is treated as a focused engineering sprint.

The task-oriented completion checklist remains in
[`ENGINEERING_CHECKLIST.md`](ENGINEERING_CHECKLIST.md).

## Engineering Charter

Project Atlas is an intelligent, modular, self-hosted entertainment platform.

Every feature should reinforce these principles:

### Simplicity over complexity

Prefer clear, understandable designs. Avoid clever implementations that increase
maintenance cost without delivering proportional value.

### Reliability over novelty

Stable behavior is more valuable than experimental behavior. Production safety
takes priority over feature speed.

### Observability before automation

Measure and explain the system before allowing it to act. Automated decisions
must be inspectable and understandable.

### Automation before manual intervention

After behavior is trusted, repetitive work should become safe, documented
automation.

### Documentation as a first-class feature

Documentation is part of the deliverable. A feature is incomplete until its
architecture, public behavior, and operational usage are documented.

### Modular architecture

Domains should be loosely coupled, independently testable, and exposed through
small public interfaces.

### Optional feature modules

Advanced behavior should be opt-in where practical. Atlas Core should remain
stable and understandable.

### User-first experience

Internal elegance must not come at the expense of usability. Atlas should be
usable by friends and family without requiring implementation knowledge.

### Evolution over replacement

- Extend before replacing.
- Refactor before rewriting.
- Preserve compatibility whenever practical.
- Migrate incrementally.
- Remove legacy behavior only after the replacement is validated.

## Sprint Workflow

Each engineering sprint follows this lifecycle:

1. Review the current repository state.
2. Review affected architecture and dependencies.
3. Define a focused scope.
4. Design public contracts before interfaces.
5. Implement incrementally.
6. Validate compatibility.
7. Run focused tests.
8. Run the relevant regression suite.
9. Execute real command validation where applicable.
10. Update architecture and user documentation.
11. Update `BUILD_LOG.md`, `CHANGELOG.md`, and `ROADMAP.md` when appropriate.
12. Clean or archive disposable development artifacts.
13. Review the complete diff.
14. Commit one focused feature or concern.
15. Push the validated branch.
16. Tag milestones only when release criteria are satisfied.

## Model Contract Standard

Every domain model should:

- normalize inputs;
- validate identity;
- validate child contracts;
- normalize timestamps to UTC;
- provide deterministic `to_dict()` serialization;
- have a dedicated test suite;
- be exported through its package `__init__.py`.

Immutable models should use frozen dataclasses unless mutation is a deliberate
part of the contract.

## Service and Provider Boundaries

Providers translate infrastructure-specific state into normalized Atlas
contracts.

Services:

- validate provider outputs;
- enforce identity and child contracts;
- aggregate normalized reports;
- preserve known domain errors;
- translate unexpected provider failures;
- remain independent of CLI, API, and Portal presentation.

CLI, API, and Portal layers should reuse service contracts instead of
duplicating business logic.

## Testing Standard

Every sprint should include the applicable layers:

1. Model tests.
2. Provider tests.
3. Service tests.
4. Interface tests.
5. Integration tests.
6. Real command validation.
7. Full or relevant regression testing.

Mock-based tests do not replace real command validation for executable
interfaces.

## Documentation Standard

Documentation should explain:

- purpose and scope;
- architecture and dependencies;
- public contracts;
- read/write boundaries;
- operational usage;
- failure behavior;
- future extension points.

Large living documents should be updated at explicit insertion points rather
than rewritten wholesale.

## Repository Layout and Tooling

The repository root is reserved for product and canonical project artifacts.

Engineering tooling belongs under:

```text
tools/
├── apply/
├── maintenance/
├── migrations/
├── release/
└── archive/
```

Temporary exports, review bundles, generated apply scripts, and other disposable
artifacts must be removed from the working tree or archived under:

```text
/mnt/storage/backups/atlas/dev-artifacts/<timestamp>/
```

Tracked files must never be moved by cleanup tooling without an explicit
migration.

## Commit Standard

Commits should:

- address one feature or concern;
- include tests and documentation for that concern;
- pass `git diff --check`;
- exclude generated exports and temporary scripts;
- use a clear conventional message where practical.

Example:

```text
feat(service-lifecycle): add read-only update discovery
```

## Release Standard

A release candidate must satisfy the engineering checklist, documented milestone
criteria, full regression testing, operational validation, repository
cleanliness, and release-note readiness.

Atlas v1.0 additionally requires the supported Administration Portal workflows
defined in the roadmap. Infrastructure write operations remain deferred until
their validated service abstractions and safety workflows are complete.

## Governance and Specifications

Atlas engineering governance is maintained under
[`governance/`](governance/README.md). Approved sprint intent and boundaries are
recorded under [`specifications/`](specifications/README.md). Permanent release
sign-off is maintained under [`releases/`](releases/README.md).

The repository is the source of truth. Conversations are engineering sessions;
decisions, specifications, implementation records, and certification belong in
the repository.

## Development Workflow

The canonical Atlas engineering workflow is documented in
[`governance/DEVELOPMENT_WORKFLOW.md`](governance/DEVELOPMENT_WORKFLOW.md).
