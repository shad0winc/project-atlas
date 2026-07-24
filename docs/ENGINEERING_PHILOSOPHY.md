# Project Atlas Engineering Philosophy

## Purpose

Project Atlas is no longer just a media server.

It is an intelligent, modular, self-hosted entertainment platform.

This document defines the engineering principles, development workflow, compatibility expectations, and completion standards that guide Project Atlas development.

Every new feature, module, integration, refactor, and release should preserve these principles.

---

## Development Philosophy

### Simplicity over complexity

Atlas should favor clear and maintainable solutions over clever or unnecessarily abstract designs.

New abstractions should exist only when they:

- solve a demonstrated problem;
- reduce duplication;
- clarify ownership or responsibility;
- improve testability;
- or establish a stable public contract.

Complexity must be justified by measurable value.

### Reliability over novelty

Stable and predictable behavior is more valuable than experimental functionality.

New features must not compromise existing behavior without an intentional, documented migration.

Atlas should fail safely when dependencies, providers, policy state, or external integrations are unavailable.

Destructive operations must default to the safest possible outcome.

### Observability before automation

Atlas must understand and expose system behavior before acting automatically.

Automated decisions should be:

- inspectable;
- explainable;
- auditable;
- measurable;
- and attributable to a policy or source.

Metrics, reports, logs, events, previews, and dry-run behavior should be introduced before unattended automation wherever practical.

### Automation before manual intervention

Once behavior is observable, validated, and trusted, repetitive operational work should be automated.

Automation should:

- reduce administrative burden;
- remain policy-driven;
- preserve user control;
- support safe failure behavior;
- and avoid surprising side effects.

Manual intervention should remain available for review, recovery, and exceptional cases.

### Documentation as a first-class feature

Documentation is part of the implementation.

A feature is not complete when its code works. It is complete when its behavior, architecture, operation, and limitations are documented appropriately.

Documentation should be updated in the same milestone or commit series as the behavior it describes.

### Modular architecture

Atlas components should have clear responsibilities and stable boundaries.

Modules and services should be:

- independently testable;
- loosely coupled;
- replaceable through documented interfaces;
- explicit about dependencies;
- and isolated from unrelated runtime behavior.

Core services should not depend on optional feature modules.

### Optional feature modules

Advanced or specialized capabilities should be optional whenever practical.

Disabling or omitting an optional module must not prevent the Atlas core from operating correctly.

Optional modules must:

- declare their dependencies;
- expose their health;
- validate their configuration;
- and fail without destabilizing unrelated services.

### User-first experience

Atlas exists to provide a dependable experience for its users.

Technical elegance must not create unnecessary difficulty for users or administrators.

Interfaces should be:

- understandable;
- consistent;
- actionable;
- safe by default;
- and clear about failures.

Friends and family should be able to use Atlas without needing to understand its internal architecture.

---

## Evolution over replacement

Atlas evolves deliberately.

Existing systems should normally be improved through incremental migration rather than immediate replacement.

Development should prefer:

- extension before replacement;
- refactoring before rewriting;
- adapters before breaking changes;
- compatibility periods before removal;
- and measured migration before retirement.

Legacy behavior may be removed only after its replacement has been:

1. implemented;
2. tested;
3. compared against the existing behavior;
4. integrated safely;
5. documented;
6. and proven through regression testing.

Temporary compatibility layers must have an explicit purpose and a documented removal condition.

---

## Engineering Lifecycle

Project Atlas features should generally mature through the following progression.

### Phase 1 — Domain

Define the domain.

Establish responsibilities, ownership, boundaries, and terminology before writing implementation code.

---

### Phase 2 — Contracts

Define immutable domain contracts.

Models establish the public language of the subsystem.

Contracts should normalize inputs, validate identities, validate nested contracts, normalize timestamps, expose stable serialization, and be fully tested.

---

### Phase 3 — Services

Implement business logic around those contracts.

Services should remain focused, deterministic, independently testable, and unaware of presentation concerns whenever practical.

---

### Phase 4 — Observability

Before introducing automation, expose the behavior through:

- reports;
- logs;
- events;
- metrics;
- previews;
- audit information; and
- dry-run execution.

Atlas should understand its behavior before acting automatically.

---

### Phase 5 — Automation

Once behavior has been validated and observed, automation may be introduced.

Automation should always remain:

- policy-driven;
- explainable;
- auditable;
- reversible where practical;
- and safe by default.

---

### Phase 6 — Integration

External providers should consume Atlas contracts rather than define them.

Atlas remains the authority for Atlas-owned policy and decision making.

---

### Phase 7 — User Experience

Only after correctness, observability, and automation are established should user-facing interfaces be expanded.

User interfaces should expose capabilities without duplicating business logic.

---

### Phase 8 — Optimization

Performance improvements should follow correctness.

Optimization should be supported by measurement rather than assumption.

Premature optimization should be avoided.

---

This lifecycle intentionally prioritizes correctness, maintainability, reliability, and observability over rapid feature delivery.

---

## Repository and Sprint Model

The GitHub repository is the source of truth for Project Atlas.

Chat conversations assist development, but repository content determines the actual state of the project.

Each engineering conversation should operate as a focused sprint.

A normal sprint follows this sequence:

1. Review the current repository state.
2. Review relevant architecture and dependencies.
3. Define the scope and compatibility requirements.
4. Design the smallest complete change.
5. Implement incrementally.
6. Run focused tests.
7. Run related regression tests.
8. Run the full test suite.
9. Validate formatting and repository state.
10. Update documentation.
11. Update the build log, roadmap, ADRs, EDRs, or changelog when appropriate.
12. Review the final diff.
13. Commit the completed milestone.
14. Push or tag when appropriate.

Unrelated changes should not be combined into the same commit.

---

## Domain Model Contract Standard

Atlas domain models should follow a consistent public contract.

Unless a documented exception is justified, every domain model must:

1. Normalize externally supplied inputs.
2. Validate required identity fields.
3. Validate nested or child contract types.
4. Enforce identity consistency across nested contracts.
5. Normalize timestamps to UTC using the `Z` suffix.
6. Provide a stable `to_dict()` serialization method.
7. Use an immutable representation where practical.
8. Raise a domain-specific error for invalid model state.
9. Have a dedicated test suite.
10. Be exported through the package's `__init__.py` when it is part of the public API.

Existing examples include:

- `PolicyDecision`
- `RetentionDecision`
- `CleanupDecision`

New models should preserve the same level of validation and serialization consistency.

---

## Compatibility Requirements

Before changing an established interface, the implementation must identify its current consumers.

Established interfaces include:

- Python public APIs;
- command-line commands;
- command output;
- JSON schemas;
- state and configuration files;
- environment variables;
- filesystem locations;
- event names and payloads;
- provider contracts;
- scheduled job identifiers;
- and documented operational procedures.

Changes should remain backward compatible whenever practical.

Additive changes are preferred over destructive schema changes.

When a breaking change is necessary, it must include:

- a documented reason;
- an explicit migration path;
- updated tests;
- updated documentation;
- and release-note visibility.

---

## Safety Requirements

Atlas must fail safely.

In particular:

- missing policy information must not authorize deletion;
- unavailable providers must not authorize deletion;
- invalid nested contracts must be rejected;
- preview and dry-run paths must not perform live mutations;
- destructive operations must be auditable;
- and optional integrations must not become the authority for Atlas policy.

External systems may request, present, or execute actions, but Atlas remains authoritative for Atlas-owned policy decisions.
