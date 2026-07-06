# Project Atlas Maturity Model

## Levels

| Level | Meaning |
|---|---|
| Level 1 | Basic functionality |
| Level 2 | Configured and operational |
| Level 3 | Integrated across the platform |
| Level 4 | Documented, monitored, and recoverable |
| Level 5 | Automated, validated, and production-ready |

---

# Domain Maturity

| Domain | Current | Goal |
|---|---:|---:|
| Infrastructure | 4 | 5 |
| Storage | 4 | 5 |
| Networking | 4 | 5 |
| Security | 4 | 5 |
| Media Management | 4 | 5 |
| Discovery | 3 | 5 |
| Presentation | 3 | 5 |
| Requests | 3 | 5 |
| Lifecycle | 3 | 5 |
| Observability | 5 | 5 |
| Operational Intelligence | 3 | 5 |
| Engineering Handbook | 4 | 5 |

---

# Atlas Retention Intelligence (ARI)

## Current Stage

**Operational Intelligence**

Atlas now observes, validates, compares, and summarizes the operational state of the media platform using immutable historical snapshots.

---

## Current Capabilities

### Platform

- Atlas version
- Hostname
- Snapshot schema version

### Storage

- Capacity
- Capacity (bytes)
- Used space
- Used space (bytes)
- Available space
- Available space (bytes)
- Utilization percentage

### Filesystem

- Media library inventory
- Library counts

### Jellyfin

- Server metadata
- Library inventory
- Library path discovery
- User inventory
- Aggregate media counts

### Validation

- Library existence validation
- Library path validation

### Analysis

- Filesystem ↔ Jellyfin synchronization
- Historical snapshot comparison
- Operational change summaries

---

## Next Stage

### Trend Analysis

- Historical storage growth
- Library growth over time
- User activity trends

### Operational Intelligence

- Configuration drift detection
- Health scoring
- Capacity forecasting
- Automated recommendations

### Automation

- Scheduled snapshot collection
- Scheduled reporting
- Automated health reports

---

## Notes

Project Atlas measures maturity by operational capability, maintainability, recoverability, automation, and engineering quality—not by the number of containers or services deployed.
