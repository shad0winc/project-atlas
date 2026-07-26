# EDR-0003 — Forecast Engine

## Status

Existing operational capability; typed timeline-based implementation in
progress.

## Context

Atlas has historically calculated storage growth, projected future usage, and
estimated storage exhaustion.

The original implementation proved the value of predictive capacity planning,
but the current analytics architecture requires forecasting to consume trusted
domain contracts rather than parse historical files directly.

Forecasts must remain honest when:

- too little history exists
- storage usage is unchanged
- storage usage decreases
- collection gaps reduce data quality
- incompatible historical snapshots are excluded
- available capacity is exhausted
- timestamps provide no useful duration

## Decision

The typed forecast engine consumes an `AnalyticsTimeline`.


```text
ARI documents
      │
      ▼
SnapshotReader
      │
      ▼
AnalyticsTimeline
      │
      ▼
StorageForecastService
      │
      ▼
ForecastSummary
```

The forecast service must not read snapshot files directly.

## Forecast Inputs

The service derives forecasts from:

- ordered historical snapshots
- timeline duration
- observed storage usage
- current usable free capacity
- library growth where applicable
- historical cadence gaps
- minimum-history requirements

Reserved filesystem capacity remains unavailable to forecast calculations.


## Forecast Calculations

For valid positive growth, Atlas calculates:

```text
growth bytes
    = latest used bytes - earliest used bytes

growth per second
    = growth bytes / timeline duration

growth per day
    = growth per second × 86,400

remaining days
    = current usable free bytes / growth per day

estimated exhaustion date
    = latest timestamp + remaining days
```

The implementation may later use robust interval averaging, but its behavior
must remain deterministic and testable.

## Unknown Forecasts

The forecast returns an explicit `unknown` state when a trustworthy estimate
cannot be produced.


Examples include:

- fewer than the required snapshots
- nonpositive timeline duration
- zero growth
- negative growth
- incompatible history
- insufficient usable-capacity information
- data-quality conditions exceeding configured limits

Atlas must not fabricate an exhaustion date in these cases.

## Health States

Forecast health uses stable domain values:

- `healthy`
- `warning`
- `critical`
- `unknown`

A preliminary threshold policy is:

    healthy   more than 180 remaining days
    warning   31 through 180 remaining days
    critical  30 or fewer remaining days
    unknown   no trustworthy estimate

Final thresholds must be centralized and covered by boundary tests.

## Gap Awareness

Timeline gaps do not automatically prevent forecasting.

The forecast must expose enough diagnostics for consumers to determine whether:

- cadence gaps exist
- history is sparse
- only a small number of intervals contributed
- rejected documents were excluded before timeline construction

Gap-aware confidence can be added without changing the timeline contract.

## Domain Contract

`ForecastSummary` must:

- normalize values
- validate child contracts
- normalize timestamps
- serialize through `to_dict()`
- use stable health values
- produce deterministic output
- remain independent of portal and API implementations

## Verification Requirements

The typed forecast implementation must test:

- normal positive growth
- timezone-aware durations
- zero growth
- negative growth
- exhausted storage
- reserved capacity
- insufficient history
- large timeline gaps

- health boundaries
- deterministic serialization
- package exports

It must also be exercised against the live 33-snapshot schema-version-1 timeline.

## Result

Atlas forecasting will consume one validated historical timeline and return an explicit, explainable capacity forecast without direct filesystem coupling.
