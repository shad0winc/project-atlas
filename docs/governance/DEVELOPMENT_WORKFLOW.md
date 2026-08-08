# Atlas Development Workflow

## Purpose

This document defines the canonical engineering workflow for Project Atlas.

## Sprint Lifecycle

```text
Repository Review
        ↓
Architecture Review
        ↓
Engineering Specification
        ↓
Scope Approval
        ↓
Implementation
        ↓
Focused Validation
        ↓
Regression Testing
        ↓
Runtime Validation (when applicable)
        ↓
Documentation Updates
        ↓
Repository Review
        ↓
Commit
        ↓
Push
```

## Scope Management

- Scope is approved before implementation.
- New ideas are deferred to future milestones unless they resolve a blocker or defect.
- One primary objective per sprint whenever practical.

## Validation Gates

Every applicable sprint includes:

- Focused validation
- Regression testing
- Runtime validation when required
- Documentation review
- Repository review
- `git diff --check`

## Completion

A sprint is complete only after implementation, validation, documentation,
repository review, commit, and push.
