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
