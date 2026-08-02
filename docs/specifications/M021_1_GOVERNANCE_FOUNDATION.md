# M-021.1 Governance Foundation — Engineering Specification

## Purpose

Establish the permanent documentation structure for Atlas engineering
governance, engineering specifications, and release certification.

## Background

Project Atlas now includes mature, independently testable domains and a
release-candidate Service Lifecycle subsystem. The project already maintains an
Engineering Guide, Engineering Checklist, Architecture documentation, Build
Log, Changelog, Roadmap, and release-audit artifacts.

M-021 formalizes the engineering method that produced those results so future
work, including the Administration Portal, follows consistent repository-owned
standards.

## Scope

M-021.1 creates the foundation only.

The sprint creates:

```text
docs/specifications/README.md
docs/specifications/M021_1_GOVERNANCE_FOUNDATION.md
docs/governance/README.md
docs/releases/README.md
```

The sprint makes small, append-only updates to:

```text
ROADMAP.md
CHANGELOG.md
docs/BUILD_LOG.md
docs/ENGINEERING_GUIDE.md
docs/ENGINEERING_CHECKLIST.md
```

## Out of Scope

This sprint does not:

- change Python source;
- change shell commands;
- change CLI behavior;
- change APIs or providers;
- change Docker or infrastructure;
- create governance policies beyond the foundation;
- certify M-021;
- implement the Administration Portal.

## Repository Changes

The permanent documentation layout begins with:

```text
docs/
├── specifications/
│   ├── README.md
│   └── M021_1_GOVERNANCE_FOUNDATION.md
├── governance/
│   └── README.md
└── releases/
    └── README.md
```

Later M-021 sprints will populate focused governance and release documents.

## Deliverables

### Specification index

`docs/specifications/README.md` defines the role of engineering
specifications.

### Governance index

`docs/governance/README.md` defines Atlas Governance and lists planned
governance documents.

### Release index

`docs/releases/README.md` defines release certification and its relationship to
the Roadmap, Changelog, Build Log, audits, and permanent certification records.

### Living-document updates

The Roadmap, Changelog, Build Log, Engineering Guide, and Engineering Checklist
record and reference the new foundation.

## Validation Requirements

The implementation must verify:

- all new files exist;
- all local Markdown links resolve;
- required living-document references exist;
- no executable source files change;
- `git diff --check` passes.

## Success Criteria

M-021.1 is complete when:

- the three permanent documentation areas exist;
- the specification is version-controlled;
- governance and release indexes are present;
- living documents reference the foundation;
- validation passes;
- the final diff contains documentation and tooling only.

## Risks

The sprint is documentation-only and has low runtime risk.

The primary risks are broken links, duplicate living-document entries, and
unintended broad rewrites. The implementation therefore uses guarded file
creation and marker-based append-only updates.

## Future Expansion

Planned M-021 work includes:

- Engineering Charter;
- Development Workflow;
- Coding Standards;
- Testing Standard;
- Documentation Standard;
- ADR Policy;
- Release Policy;
- Versioning;
- Contributing guidance;
- Release Certification template;
- M-018 Service Lifecycle certification;
- Governance audit.

## References

- [`../ENGINEERING_GUIDE.md`](../ENGINEERING_GUIDE.md)
- [`../ENGINEERING_CHECKLIST.md`](../ENGINEERING_CHECKLIST.md)
- [`../BUILD_LOG.md`](../BUILD_LOG.md)
- [`../../CHANGELOG.md`](../../CHANGELOG.md)
- [`../../ROADMAP.md`](../../ROADMAP.md)
- [`../architecture/SERVICE_LIFECYCLE.md`](../architecture/SERVICE_LIFECYCLE.md)
