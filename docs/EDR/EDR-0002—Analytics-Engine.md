# EDR-0002 — Analytics Engine

## Status

Implemented and undergoing typed-pipeline hardening.

## Context

Atlas Retention Intelligence originally produced immutable JSON snapshots and
performed analytics directly against historical snapshot documents.

That approach established useful historical reporting, but it coupled
filesystem access, document parsing, timeline construction, comparisons, and
forecasting too closely.

The analytics subsystem now requires stable domain contracts that can be reused
by the API, portal, forecast engine, recommendations, health reporting, and
future backup observability.

Historical ARI data also contains multiple document generations:

- legacy documents without the current top-level `atlas` object
- early schema documents containing incompatible storage value types
- one malformed historical JSON document
- current schema-version-1 documents

Invalid historical documents must remain visible without contaminating trusted
analytics results.

## Decision

Atlas uses an explicit analytics pipeline:

```text
ARI JSON documents
        │
        ▼
SnapshotReader
        │
        ▼
ARISnapshot
        │
        ▼
AnalyticsTimelineBuilder
        │
        ▼
AnalyticsTimeline
        │
        ├── chronological ordering
        ├── timezone-aware timestamps
        ├── duplicate rejection
        ├── schema consistency
        ├── interval calculation
        └── cadence-gap detection
        │
        ▼
AnalyticsComparisonService
        │
        ▼
AnalyticsSnapshot

Each layer has one responsibility.

### Snapshot Reader

`SnapshotReader`:

- reads ARI JSON documents
- validates document structure
- normalizes timestamps
- validates storage and library values
- produces an `ARISnapshot`
- rejects malformed or incompatible documents explicitly

The reader does not perform forecasting or historical analysis.

### Analytics Timeline

`AnalyticsTimelineBuilder`:

- accepts validated `ARISnapshot` instances
- orders snapshots by timezone-aware timestamps
- rejects duplicate instants
- requires one common schema version
- calculates intervals between adjacent snapshots
- derives expected cadence from the median interval when not configured
- identifies abnormal collection gaps
- preserves gaps as observable metadata rather than treating them as fatal

An `AnalyticsTimeline` requires at least two compatible snapshots.


### Comparison Service

`AnalyticsComparisonService` compares trusted snapshots and produces normalized
storage and library-growth results.

The comparison service does not read files and does not discover history.

## Domain Contracts

Analytics domain models follow the Atlas model contract:

- normalized inputs
- identity validation
- child-contract validation
- timezone-aware timestamps
- deterministic `to_dict()` serialization
- dedicated tests
- public package exports

## Historical Data Validation

The timeline implementation was validated against live ARI history on
July 26, 2026.

Observed history:

- 44 JSON documents inspected
- 33 compatible schema-version-1 snapshots
- 11 rejected historical documents
- 2 historical cadence gaps detected
- median observed cadence of 86,335 seconds


The rejected documents consisted of:

- 4 legacy documents without a top-level `atlas` object
- 6 documents with incompatible storage-capacity value types
- 1 malformed or empty JSON document

Rejected documents remain preserved for future migration and reliability
testing.

## Consequences

### Benefits

- Forecasting no longer requires direct filesystem access.
- Portal and API consumers share stable analytics contracts.
- Historical gaps become observable.
- Invalid documents cannot silently alter forecasts.
- Timezone offsets are handled consistently.
- Future moving averages and anomaly detection can reuse the timeline.

### Tradeoffs

- Legacy snapshots require migration or explicit quarantine before inclusion.
- Timeline construction currently rejects mixed schema versions.
- Forecast confidence must account for historical gaps and excluded input.


## Verification

The timeline slice was verified by:

- 74 focused analytics tests
- 636 complete core tests
- 5 passing Sports integration suites
- live construction of a 33-snapshot analytics timeline

## Result

Atlas now converts compatible ARI history into a validated, ordered, and
gap-aware timeline suitable for comparison and forecasting.
