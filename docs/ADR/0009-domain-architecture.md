# ADR 0009 — Atlas Domain Architecture

## Status

Accepted

## Scope

This ADR establishes the architectural standards for Atlas Core domains.

It defines the structure, responsibilities, and implementation contracts that
all Atlas business domains must follow. These standards ensure that new
features integrate consistently with the existing platform while remaining
easy to understand, test, and maintain.

This ADR applies to current and future Atlas domains, including but not limited
to:

- Discovery
- Identity
- Scheduler
- Retention
- Cleanup
- Analytics
- Media
- Events
- Sports

Future ADRs may extend these standards but should not redefine them without
explicitly superseding this decision.

---

## Context

Project Atlas has grown from a media stack into a modular software platform.

Recent development introduced dedicated domains for retention, cleanup,
identity, scheduling, analytics, and portal functionality. As additional
domains are introduced, Atlas requires a consistent architectural approach that
reduces duplication, improves maintainability, and keeps business logic
independent of infrastructure concerns.

Without a common architecture, individual domains may evolve inconsistent
layouts, testing strategies, or dependency relationships.

---

## Decision

Atlas Core adopts a domain-first architecture.

Each domain represents a single business capability and is responsible for its
own models, services, providers, and reporting.

Business logic must remain independent from presentation layers and external
integrations.

---

## Design Principles

Atlas Core domains should favor:

- Simplicity over unnecessary abstraction.
- Reliability over novelty.
- Explicit contracts over implicit behavior.
- Composition over duplication.
- Observability before automation.
- Testability as a first-class design goal.

Architectural consistency should take precedence over feature-specific
optimizations unless a documented exception exists.

---

## Standard Package Layout

Each domain should follow the standard package layout whenever applicable.

```text
atlas/<domain>/
    __init__.py
    models.py
    service.py
    providers.py
    report.py        # Optional
    cli.py           # Optional
```

Additional modules may be added when justified by complexity, but unnecessary
nesting should be avoided.

---

## Domain Responsibilities

A domain owns exactly one business capability.

Domains should expose well-defined public interfaces and should not depend on
the internal implementation details of other domains.

Examples include:

- Discovery
- Retention
- Cleanup
- Identity
- Scheduler

Domains should communicate through well-defined interfaces rather than sharing
implementation details.

---

## Model Responsibilities

Domain models are responsible for:

- Input normalization
- Identity validation
- Child object validation
- Timestamp normalization
- Serialization through `to_dict()`

Models must remain independent of CLI, HTTP, or provider implementations.

---

## Service Responsibilities

Services coordinate business workflows.

Services may:

- Validate business operations
- Coordinate models
- Invoke providers
- Produce domain reports

Services must not:

- Format CLI output
- Generate HTTP responses
- Contain presentation logic

---

## Provider Responsibilities

Providers encapsulate communication with external systems.

Examples include:

- Jellyfin
- Prowlarr
- Sonarr
- Radarr
- Maintainerr

Providers normalize external responses into Atlas domain models.

Business rules must remain inside services rather than providers.

---

## CLI Responsibilities

The CLI serves as a thin presentation layer.

The dependency flow is:

```text
CLI
    │
    ▼
Service
    │
    ▼
Provider
    │
    ▼
External System
```

CLI commands should validate user input and delegate business behavior to the
appropriate service.

---

## Testing Requirements

Every domain must include dedicated unit tests.

At minimum, tests should verify:

- Model validation
- Model serialization
- Service behavior
- Provider behavior (where applicable)

Tests should remain isolated and deterministic.

---

## Export Conventions

Public domain objects should be exported through the package's
`__init__.py` file.

Consumers should import public interfaces from the package rather than
individual implementation modules whenever practical.

---

## Consequences

### Benefits

- Consistent architecture across Atlas
- Easier onboarding for contributors
- Reduced code duplication
- Improved maintainability
- Predictable testing strategy
- Cleaner dependency boundaries
- Simplified future expansion

### Tradeoffs

- Slightly more structure for small domains
- Additional documentation requirements
- Higher expectation for architectural consistency

---

## Relationship to Other ADRs

This ADR complements:

- ADR 0001 — Atlas Platform Architecture
- ADR 0008 — Atlas Portal Architecture

ADR 0001 defines the high-level platform organization.

ADR 0008 defines the architecture between the Portal, API, and Atlas Core.

This ADR defines the architectural conventions used within Atlas Core itself.

