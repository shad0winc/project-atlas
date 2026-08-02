# Atlas Engineering Sprint Checklist

For engineering principles, repository layout, and workflow standards, see [`ENGINEERING_GUIDE.md`](ENGINEERING_GUIDE.md).

This checklist is the standard completion contract for Project Atlas engineering
sprints. A sprint is not complete until every applicable item has been reviewed.

## Discovery and Design

- [ ] Repository state reviewed.
- [ ] Current branch and intended scope confirmed.
- [ ] Architecture and dependency boundaries reviewed.
- [ ] Compatibility and migration requirements identified.
- [ ] Read-only and mutation boundaries explicitly confirmed.

## Domain Contracts

- [ ] Inputs are normalized.
- [ ] Identity is validated.
- [ ] Child contracts are validated.
- [ ] Timestamps are normalized.
- [ ] Public models provide `to_dict()`.
- [ ] Public symbols are exported through the package `__init__.py`.
- [ ] Dedicated model tests are present.

## Implementation

- [ ] Implementation is incremental and scoped to one concern.
- [ ] Existing public behavior is preserved where practical.
- [ ] Provider, service, interface, and presentation responsibilities remain separate.
- [ ] Mutations are guarded by explicit validation and safety controls when applicable.
- [ ] Rollback or recovery paths are documented when applicable.

## Validation

- [ ] Python compilation passes.
- [ ] Shell syntax validation passes.
- [ ] Focused tests pass.
- [ ] Related subsystem regression tests pass.
- [ ] Full repository regression tests pass.
- [ ] Real command or integration validation passes.
- [ ] Machine-readable output is parsed and contract-checked.
- [ ] `git diff --check` is clean.
- [ ] The working tree contains only intentional changes.

## Documentation and Release Records

- [ ] Architecture documentation is updated.
- [ ] CLI and API documentation are updated when applicable.
- [ ] `docs/BUILD_LOG.md` is updated.
- [ ] `CHANGELOG.md` is updated.
- [ ] `ROADMAP.md` is updated when scope or release criteria change.
- [ ] Commit scope and message are focused.
- [ ] Push and milestone tagging are completed when appropriate.

## Engineering Principles

Every sprint should reinforce:

- Simplicity over complexity.
- Reliability over novelty.
- Observability before automation.
- Automation before manual intervention.
- Documentation as a first-class feature.
- Modular architecture.
- Optional feature modules.
- User-first experience.
- Evolution over replacement.

## Governance Foundation Gate

For applicable sprints:

- [ ] An engineering specification defines scope and exclusions.
- [ ] Governance and release requirements have been reviewed.
- [ ] Repository documentation remains the authoritative record.
- [ ] Deferred improvements are recorded outside the active sprint scope.

## Engineering Charter Review

- [ ] The sprint preserves the Atlas Engineering Charter.
- [ ] Scope remained locked after approval unless a concrete blocker or defect required change.
- [ ] The repository is the authoritative record of durable decisions.
- [ ] The sprint leaves the repository more maintainable than it found it.
