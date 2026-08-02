# Atlas Release Certification

Release certification is the permanent engineering sign-off for an Atlas
subsystem or product release.

A certification records:

- delivered scope;
- architecture and public interfaces;
- testing and runtime validation;
- documentation coverage;
- compatibility guarantees;
- repository health;
- known intentional limitations;
- integration guidance;
- certification result.

## Relationship to Other Records

- `ROADMAP.md` defines planned and completed milestones.
- `CHANGELOG.md` records notable user- and developer-visible changes.
- `docs/BUILD_LOG.md` records chronological implementation history.
- Audit artifacts contain detailed validation evidence.
- Release certifications summarize the approved result as a permanent,
  version-controlled record.

## Planned Files

```text
TEMPLATE.md
RC_M018_SERVICE_LIFECYCLE.md
RC_V1_0.md
```

Future certification documents must be based on completed validation evidence.
Certification does not replace tests, runtime validation, documentation, or
repository review.

## Certification Boundary

A subsystem is not certified merely because implementation is complete.
Certification requires the applicable engineering gates, including tests,
runtime validation, documentation, repository audit, review, commit, and push.
