# Project Atlas Maturity Model

## Levels

| Level | Meaning |
|---|---|
| Level 1 | Basic functionality |
| Level 2 | Configured and working |
| Level 3 | Integrated with platform |
| Level 4 | Documented, monitored, recoverable |
| Level 5 | Fully automated, tested, production-ready |

## Domain Maturity

| Domain | Current | Goal |
|---|---:|---:|
| Infrastructure | 4 | 5 |
| Storage | 4 | 5 |
| Networking | 4 | 5 |
| Security | 4 | 5 |
| Media Management | 3 | 5 |
| Discovery | 2 | 5 |
| Presentation | 2 | 5 |
| Requests | 2 | 5 |
| Lifecycle | 2 | 5 |
| Observability | 3 | 5 |
| Operations | 1 | 5 |
| Engineering Handbook | 4 | 5 |

## Atlas Retention Intelligence (ARI)

### Current Stage

**Operational Observability**

Atlas can currently observe, normalize, and validate the operational state of the media platform.

### Current Capabilities

#### Platform

- Atlas version
- Hostname
- Snapshot schema version

#### Storage

- Capacity
- Used space
- Available space
- Utilization percentage

#### Filesystem

- Media library inventory
- Library counts

#### Jellyfin

- Server metadata
- Library inventory
- Library path discovery
- User observation

#### Validation

- Library existence validation
- Library path validation

### Next Stage

**Operational Intelligence**

Future milestones include:

- Filesystem ↔ Jellyfin item comparison
- Snapshot trend analysis
- Storage growth forecasting
- User activity analytics
- Retention recommendations

## Notes

Maturity measures maintainability, recoverability, automation, and operational clarity — not container count.
