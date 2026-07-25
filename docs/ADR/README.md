# Atlas Architecture Decision Records (ADRs)

## Purpose

Architecture Decision Records (ADRs) document significant architectural and
technical decisions made throughout the development of Project Atlas.

Each ADR captures:

- The problem being solved.
- The decision that was made.
- Alternatives that were considered.
- The long-term consequences of the decision.

Together, the ADRs provide the architectural history of the project.

## Naming Convention

Project Atlas currently contains ADRs from two documentation eras.

### Legacy Format

Early ADRs use the original naming convention:

    ADR-0001-...
    ADR-0002-...
    ADR-0003-...

These files are intentionally retained unchanged to preserve repository
history and existing references.

### Current Format

Beginning with ADR 0008, Atlas adopts the simplified naming convention:

    0008-description.md
    0009-description.md
    0010-description.md

All new ADRs must follow this format.

## Documentation Hierarchy

The documentation is organized as follows:

- docs/ADR
    Records why architectural decisions were made.

- docs/architecture
    Describes how Atlas is currently designed.

ADRs explain the reasoning behind architectural decisions, while the
architecture documents describe the current implementation.

## Status

Both naming conventions are considered valid historical records.

The simplified numeric format is the project standard for all future ADRs.
