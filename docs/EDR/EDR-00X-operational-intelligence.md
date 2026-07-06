# Operational Intelligence

## Decision

Atlas Retention Intelligence stores immutable historical snapshots and derives operational insights by comparing snapshots rather than mutating historical data.

## Rationale

- Preserves historical integrity
- Enables trend analysis
- Simplifies debugging
- Supports future recommendations

## Consequences

All future ARI analyzers should operate on immutable snapshots.
