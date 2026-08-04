# Project Atlas Maturity Model

Project Atlas measures maturity by **operational capability**, **reliability**, **automation**, **maintainability**, and **engineering quality** rather than by the number of deployed services.

---

# Maturity Levels

| Level | Description |
|--------|-------------|
| **Level 1** | Functional — Core functionality exists. |
| **Level 2** | Operational — Configured, stable, and usable. |
| **Level 3** | Integrated — Services operate as a unified platform. |
| **Level 4** | Observable — Health, monitoring, validation, and recovery are implemented. |
| **Level 5** | Intelligent — Automated, predictive, self-validating, and production ready. |

---

# Domain Maturity

| Domain | Current | Goal |
|---------|:------:|:----:|
| Infrastructure | **5** | 5 |
| Storage | **5** | 5 |
| Networking | **5** | 5 |
| Security | **4** | 5 |
| Media Management | **5** | 5 |
| Discovery | **5** | 5 |
| Presentation | **4** | 5 |
| Requests | **4** | 5 |
| Lifecycle Management | **5** | 5 |
| Observability | **5** | 5 |
| Operational Intelligence | **5** | 5 |
| Documentation | **5** | 5 |

---

# Atlas Retention Intelligence (ARI)

## Status

**Production Ready**

ARI is the operational intelligence subsystem of Project Atlas.

It continuously evaluates platform health, analyzes historical operational data, forecasts future capacity requirements, and provides actionable recommendations.

The original ARI analytics and forecast capabilities are operational. Atlas has
hardened those capabilities behind typed, independently tested domain services.
The typed snapshot reader, comparison service, analytics timeline, and
timeline-based forecast service are implemented and validated. Future work will
focus on forecast refinement, confidence reporting, and additional forecasting
strategies without changing the established timeline contract.

---

# Engine Architecture

ARI consists of four independent engines.

## Health Engine

### Capabilities

- Platform health scoring
- Docker validation
- Storage validation
- VPN validation
- Jellyfin validation
- Snapshot freshness monitoring

Result:

ARI continuously evaluates the operational health of Atlas.

---

## Analytics Engine

### Capabilities

- Immutable snapshots
- Historical storage analysis
- Historical library analysis
- Trend detection
- Historical comparisons
- Operational summaries

Result:

ARI understands historical platform behavior.

---

## Forecast Engine

### Capabilities

- Time-normalized growth analysis
- Average storage growth
- Average daily growth
- Capacity forecasting
- Days remaining estimation
- Estimated storage exhaustion date
- Forecast confidence analysis

Result:

ARI predicts future storage requirements using historical operational data.

---

## Recommendation Engine

### Capabilities

- Health recommendations
- Capacity recommendations
- Forecast recommendations

Result:

ARI provides actionable operational guidance.

---

# Current Platform Capabilities

## Infrastructure

- Docker orchestration
- Proxmox LXC deployment
- Intel Quick Sync
- VPN networking
- Operational CLI
- Backup framework

## Media Platform

- Jellyfin
- Jellyseerr
- Sonarr
- Sonarr Anime
- Radarr
- Radarr Anime
- Prowlarr
- Recyclarr
- Bazarr
- Maintainerr
- qBittorrent
- Homepage
- Dozzle

## Operational Intelligence

- Health monitoring
- Historical analytics
- Capacity forecasting
- Recommendation engine

---

# Current Maturity Assessment

Project Atlas has achieved:

- Production-ready infrastructure
- Production-ready media platform
- Production-ready operational intelligence
- Comprehensive documentation
- Version-controlled configuration
- Automated validation
- Operational forecasting

Overall Project Maturity:

# **Level 5 — Intelligent**

Atlas has evolved from a self-hosted media server into an intelligent operational platform capable of monitoring, validating, forecasting, and recommending actions based on real operational data.

---

# Next Evolution

The next stage of Project Atlas focuses on expanding platform capabilities rather than increasing maturity.

## Planned

### Atlas Platform

- Web dashboard
- Administrative portal
- User portal
- REST API

### User Intelligence

- Favorites
- Protected media
- Watch history
- Personalized recommendations

### Smart Automation

- Automatic TV episode subscriptions
- Live sports integration
- Notification framework

### Long-Term

- Multi-server deployments
- Distributed storage
- Plugin architecture
- Mobile companion
- AI-assisted operational insights

---

# Engineering Philosophy

Project Atlas prioritizes:

- Simplicity over complexity
- Reliability over novelty
- Observability before automation
- Automation before manual intervention
- Intelligence through operational data
- Documentation as a first-class feature

# Atlas API Contract Foundation

## Status

**Implemented — Shared Contract and Adapter Foundation Complete**

Implemented capabilities include:

- canonical API and schema version constants;
- a stable vendor media type;
- immutable transport-neutral API errors;
- immutable success and failure response envelopes;
- normalized UTC response timestamps;
- validated response reconstruction;
- deterministic JSON-compatible serialization;
- mapping, sequence, enum, dataclass, datetime, and `to_dict()` support;
- explicit rejection of unsupported and framework-specific values;
- stable public exports through `atlas.api`;
- Pydantic and OpenAPI envelope schemas under `apps/api`;
- reusable FastAPI success and failure envelope helpers;
- opt-in adoption for new HTTP routes;
- backward compatibility for existing unwrapped endpoint responses;
- cross-contract validation with Operations reports and comparisons;
- dedicated shared-contract, integration, adapter, schema, and endpoint
  regression tests.

The shared API contract layer is **Level 4 — Observable**.

Its contracts are deterministic, versioned, test-backed, and ready for use by
new HTTP endpoints. The layer remains independent of FastAPI, Pydantic,
Starlette, routers, HTTP request objects, and status codes.

The existing FastAPI application owns HTTP routing, request parsing,
authentication, authorization, Pydantic validation, and OpenAPI generation.

Operations HTTP routes, broader envelope adoption, endpoint migration, and
Portal visualization remain planned extensions.

---

# Atlas Operations Reporting

## Status

**Implemented — Persistent CLI Complete**

Implemented capabilities include:

- immutable Operations findings, sections, summaries, and reports;
- schema-validated report deserialization;
- read-only System and Docker collectors;
- guarded Docker execution and normalized provider snapshots;
- runtime, health, restart, OOM, exit, and governance findings;
- deterministic aggregation and collector failure isolation;
- automatic runtime-context discovery;
- detailed human-readable and stable JSON reports;
- immutable timestamped report snapshots;
- atomic `latest.json` persistence;
- duplicate-snapshot protection;
- newest-first repository history support;
- configurable bounded history inspection;
- concise human-readable history output;
- stable wrapped JSON history output;
- immutable finding-change and aggregate comparison contracts;
- deterministic added, removed, changed, and unchanged detection;
- derived status, score, attention, and change summaries;
- concise human and stable JSON comparison rendering;
- shared `TaskScheduler` integration;
- canonical hourly `operations.collect` registration;
- idempotent core-task synchronization with runtime-state preservation;
- isolated scheduled-collection subprocess execution;
- core-task isolation from optional-module event routing;
- configurable scheduled repository roots through
  `ATLAS_OPERATIONS_DIRECTORY`;
- public `atlas operations report`, `save`, `latest`, `history`, and
  `compare` commands;
- public scheduler synchronization, inspection, execution, and history
  workflows for scheduled Operations collection;
- validated compatibility with the shared transport-neutral API contract;
- deterministic serialization through shared API response envelopes;
- dedicated unit, integration, regression, corruption, atomic-write,
  comparison, renderer, scheduler, subprocess, shell, API-contract, and live
  validation.

The subsystem is **Level 4 — Observable** with durable report
persistence and automated scheduled collection.

Operations HTTP route exposure, notifications, and Portal visualization
remain planned extensions. The shared API contract and FastAPI adapter
foundations are implemented, but no Operations endpoint is claimed complete.
