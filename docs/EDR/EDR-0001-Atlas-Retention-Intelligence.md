# EDR-0001: Atlas Retention Intelligence (ARI)

**Status:** Accepted  
**Date:** 2026-07-05  
**Authors:** Project Atlas

---

# Summary

Atlas Retention Intelligence (ARI) provides the data collection and analysis foundation for Project Atlas.

ARI is responsible for observing the state of the Atlas platform, collecting operational data, and producing immutable Atlas Snapshots that serve as the canonical representation of the system at a point in time.

ARI does **not** modify external services. It is intentionally designed as a read-only subsystem.

---

# Motivation

Atlas requires a consistent, extensible way to understand:

- Storage utilization
- Media libraries
- User activity
- Library growth
- Retention trends

Rather than querying multiple services independently each time, ARI normalizes collected information into a single snapshot format.

This provides a stable foundation for reporting, analytics, forecasting, and future automation.

---

# Architecture

ARI follows an adapter-based architecture.

```text
Filesystem Adapter
        │
        ▼

Atlas Snapshot

        ▲
        │

Jellyfin Adapter

        ▲
        │

Sonarr Adapter

        ▲
        │

Radarr Adapter

        ▲
        │

Maintainerr Adapter
```

Each adapter contributes data to a single Atlas Snapshot.

Adapters remain independent and do not communicate directly with one another.

---

# Atlas Snapshots

Atlas Snapshots are immutable.

Each snapshot represents the complete observed state of Atlas at a specific point in time.

Snapshots are stored under:

```text
/mnt/storage/configs/atlas/ari/snapshots/
```

The most recent snapshot is copied to:

```text
latest.json
```

for convenient access.

Historical snapshots are never modified.

---

# Snapshot Schema

Atlas Snapshots are versioned independently from Atlas releases.

Example:

```json
{
  "timestamp": "...",

  "atlas": {
    "version": "0.5.0",
    "schema_version": 1
  },

  "storage": { },

  "libraries": { }
}
```

The snapshot schema is expected to evolve while remaining backward compatible whenever practical.

---

# Runtime Data

ARI runtime state intentionally lives outside the Git repository.

Runtime location:

```text
/mnt/storage/configs/atlas/
```

This keeps source code separate from operational state and allows runtime information to survive repository updates and fresh clones.

---

# JSON Processing

Atlas standardizes on `jq` for JSON processing.

All future ARI modules should use `jq` when reading, querying, or presenting JSON data.

---

# Design Principles

ARI follows these principles:

- Observe, never modify.
- Normalize data before analysis.
- Keep snapshots immutable.
- Separate collection from presentation.
- Keep adapters independent.
- Build incrementally.

---

# ARI Reasoning Model

ARI separates platform intelligence into four stages:

## Observation

An observation is a fact collected from Atlas or an external service.

Examples:

- Jellyfin reports a library named `Movies`.
- The filesystem contains `/mnt/storage/media/Movies`.
- Available storage is `1.7T`.

Observations must be read-only and should not contain judgments.

## Validation

A validation compares observations against expected Atlas configuration.

Examples:

- Jellyfin has all expected libraries.
- Jellyfin library paths match expected container paths.
- Required storage paths are writable.

Validations may produce `PASS`, `WARN`, or `FAIL`.

## Recommendation

A recommendation explains what the operator should consider doing.

Examples:

- Re-scan a Jellyfin library.
- Correct a mismatched library path.
- Review unused media.

Recommendations do not modify the system.

## Action

An action changes system state.

Examples:

- Delete media.
- Modify a Jellyfin library.
- Apply a retention rule.

Actions require explicit operator approval and are outside the scope of the initial ARI implementation.

---

# Future Work

Planned enhancements include:

- Filesystem analytics
- Historical storage growth
- Jellyfin adapter
- Sonarr adapter
- Radarr adapter
- Maintainerr adapter
- User activity analysis
- Retention recommendations
- Forecasting engine

These enhancements will extend the Atlas Snapshot rather than replace it.

---

# Decision

Project Atlas adopts Atlas Snapshots as the canonical data model for operational intelligence.

All future ARI functionality will build upon this snapshot architecture.
