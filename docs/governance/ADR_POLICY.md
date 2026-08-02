# Atlas ADR Policy

## Purpose

This document defines the canonical policy for Architecture Decision Records
(ADRs) in Project Atlas.

ADRs preserve significant architectural decisions so future engineers can
understand not only what Atlas does, but why the architecture exists in its
current form.

## ADR Philosophy

Architecture decisions are durable engineering knowledge.

They must outlive individual conversations, implementation sessions, and
contributors. ADRs reduce repeated debate, prevent accidental reversal of
important constraints, and make architectural tradeoffs visible.

ADRs are not created for ceremony. They are created when preserving the
decision materially improves stability, reliability, maintainability,
operational clarity, or long-term understanding.

## When an ADR Is Required

An ADR is required when a decision materially affects one or more of the
following:

- subsystem boundaries;
- public APIs or serialized contracts;
- provider abstractions;
- service-layer responsibilities;
- persistence strategy;
- authentication or authorization;
- deployment topology;
- infrastructure ownership;
- compatibility strategy;
- cross-domain data flow;
- safety boundaries;
- long-lived dependency choices;
- migration strategy;
- release architecture;
- operational recovery design.

An ADR is also required when reversing or superseding an accepted architectural
decision.

## When an ADR Is Not Required

An ADR is usually not required for:

- bug fixes that preserve existing architecture;
- typo or formatting corrections;
- routine dependency maintenance;
- local refactors that do not change public contracts;
- test-only changes;
- documentation-only clarifications;
- implementation details already governed by an accepted ADR;
- temporary investigation code;
- one-off operational commands.

When uncertain, prefer the smallest documentation artifact that preserves the
necessary reasoning.

## ADR Location and Naming

ADRs live under:

```text
docs/ADR/
```

Files should use a stable numeric identifier and descriptive title:

```text
0001-short-decision-title.md
```

Identifiers are never reused.

Renaming an accepted ADR should be avoided unless correcting a clear defect.

## ADR Lifecycle

The standard ADR lifecycle is:

```text
Proposed
↓
Accepted
↓
Implemented
↓
Superseded or Deprecated
↓
Archived
```

Not every ADR reaches every state.

## Status Values

Supported ADR status values are:

- **Proposed** — under review and not yet authoritative.
- **Accepted** — approved and authoritative.
- **Implemented** — accepted and reflected in the repository.
- **Superseded** — replaced by a newer ADR.
- **Deprecated** — retained for compatibility or history but no longer preferred.
- **Rejected** — reviewed and intentionally not adopted.
- **Archived** — retained only as historical context.

The current status must appear near the top of the ADR.

## Required Sections

Every ADR must contain:

1. Title
2. Status
3. Date
4. Context
5. Decision
6. Rationale
7. Alternatives Considered
8. Consequences
9. Validation
10. Related Work

Additional sections may be added when they improve understanding.

## Context

The Context section should explain:

- the problem;
- relevant constraints;
- current behavior;
- affected users or operators;
- architectural pressure;
- why a durable decision is necessary.

Context should be specific enough that the decision remains understandable
without relying on conversation history.

## Decision

The Decision section states the chosen architecture clearly.

It should identify:

- the selected approach;
- the affected boundaries;
- responsibilities;
- compatibility expectations;
- safety limits;
- implementation obligations.

Avoid vague statements that cannot be validated.

## Rationale

The Rationale section explains why the selected option best fits Atlas.

The rationale should be grounded in Atlas priorities:

- stability;
- reliability;
- maintainability;
- operational simplicity;
- user experience;
- compatibility;
- repository clarity.

Novelty alone is never sufficient rationale.

## Alternatives Considered

Record meaningful alternatives and why they were not selected.

Alternatives may include:

- preserving the current design;
- using a different abstraction;
- adopting a different dependency;
- deferring the decision;
- choosing a simpler implementation.

Do not invent weak alternatives solely to make the chosen decision appear
stronger.

## Consequences

Consequences should describe both benefits and costs.

Include applicable:

- implementation impact;
- migration work;
- compatibility obligations;
- operational burden;
- testing requirements;
- documentation requirements;
- future limitations;
- follow-up decisions.

Accepted tradeoffs should be explicit.

## Validation

The ADR should define how the decision will be validated.

Applicable validation may include:

- focused tests;
- regression tests;
- public contract tests;
- runtime validation;
- migration validation;
- compatibility checks;
- repository review;
- release audit.

A decision is not considered implemented merely because code exists.

## Related Work

Link to applicable:

- engineering specifications;
- architecture documentation;
- implementation milestones;
- related ADRs;
- EDRs;
- API documentation;
- CLI documentation;
- release certification;
- migration notes.

Links should point to authoritative repository documents.

## Relationship to Engineering Specifications

Specifications define approved sprint scope and deliverables.

ADRs define durable architectural decisions.

A specification may reference an existing ADR or require a new ADR.

A specification should not silently redefine an accepted ADR.

When implementation reveals that an accepted decision must change, update the
architecture through a new or superseding ADR rather than rewriting history.

## Relationship to Architecture Documentation

Architecture documentation explains the current system.

ADRs explain why key architectural choices were made.

Architecture documents should reflect implemented ADRs and link to them when
the decision materially affects the design.

ADRs should not duplicate the full operational or API documentation of a
subsystem.

## Relationship to Governance

The Engineering Charter and governance standards define how decisions are made
and recorded.

An ADR must comply with:

- the Engineering Charter;
- the Development Workflow;
- the Coding Standards;
- the Testing Standard;
- the Documentation Standard.

If an ADR conflicts with governance, the conflict must be resolved explicitly.

## Relationship to Release Documentation

Release certification may reference ADRs that define the certified
architecture.

A release must not claim architectural stability when required ADRs remain
unresolved or implementation does not match accepted decisions.

## Review Expectations

ADR review should confirm:

- the decision is architectural and durable;
- scope is clear;
- rationale reflects Atlas priorities;
- alternatives are represented fairly;
- consequences include costs as well as benefits;
- compatibility and safety effects are explicit;
- validation is concrete;
- related documents are linked;
- status is correct.

Review should focus on decision quality, not only wording.

## Approval

An ADR becomes Accepted only after explicit review and approval by the project
owner or authorized maintainers.

Implementation may begin while an ADR is Proposed only when the work is clearly
experimental and does not create an unsupported public contract.

## Implementation

When an ADR is implemented:

- update its status to Implemented;
- ensure the repository reflects the decision;
- complete required tests;
- update related architecture, API, CLI, and operational documentation;
- update the Build Log and Changelog when appropriate;
- preserve compatibility or document migration.

## Superseding an ADR

Do not rewrite an accepted ADR to hide a changed decision.

Create a new ADR that:

- references the earlier ADR;
- explains why the decision changed;
- records the new context;
- documents migration and consequences.

Update the earlier ADR status to Superseded and link to the replacement.

## Deprecation and Archival

Deprecated ADRs remain relevant when supported legacy behavior still exists.

Archived ADRs remain available for historical context but are not active
architecture.

Archival must not remove information required to understand current
compatibility or migration behavior.

## ADR Template

Use this structure:

```markdown
# ADR-XXXX — Decision Title

**Status:** Proposed
**Date:** YYYY-MM-DD

## Context

## Decision

## Rationale

## Alternatives Considered

## Consequences

## Validation

## Related Work
```

Additional sections may be added when justified.

## Validation Requirements

ADR documentation should validate:

- required headings;
- status value;
- date format;
- local links;
- related ADR references;
- governance consistency;
- architecture consistency;
- `git diff --check`.

Implemented ADRs should also be validated against the actual repository state.

## Repository Review

Before commit, review:

```text
git status --short
git diff --check
git diff --stat
git diff
```

Untracked ADRs must be reviewed directly because normal `git diff` does not show
their contents.

## Definition of ADR Complete

An ADR is complete only when every applicable condition is satisfied:

- context is documented;
- the decision is explicit;
- rationale reflects Atlas priorities;
- meaningful alternatives are recorded;
- consequences are documented;
- validation is defined;
- related work is linked;
- status is correct;
- approval is recorded;
- implementation matches the decision when marked Implemented;
- repository validation passes.

A significant architectural decision that exists only in conversation or code
comments is not complete Atlas work.
