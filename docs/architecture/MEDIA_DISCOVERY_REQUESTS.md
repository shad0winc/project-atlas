# Media Discovery and Request Safety

## Purpose

This document defines the implemented Atlas boundary for Media discovery,
Personal Request creation, duplicate/race protection, and Portal request
presentation through M-023.27.3B3.

The design keeps provider-specific discovery and mutation behind Atlas. Browser
clients consume normalized Atlas contracts and never become trusted provider
clients.

## Current Source Checkpoint

The B3 implementation is represented by six atomic commits:

- `755409de` — Seerr-backed Media discovery foundation;
- `7bd4a14a` — Personal Media browse/search Portal;
- `28cbb790` — active Request uniqueness and race protection;
- `b1c2ebcb` — movie Request action in the Portal;
- `b901702d` — TV-series detail and season metadata; and
- `c1bbe9d5` — explicit TV/anime-TV routing and submission preflight.

These are source/repository changes. They do not, by themselves, certify a
production deployment or the remaining v1.0 user-acceptance gates.

## System Boundary

```text
Browser
  |
  v
Atlas Portal
  |
  v
Atlas API
  |
  +------------------------+
  |                        |
  v                        v
Media discovery        Media Request service
  |                        |
  +-----------+------------+
              |
              v
        Seerr provider boundary
              |
              v
   Media automation / acquisition
```

The Portal never connects directly to Seerr. Atlas owns authentication,
authorization, normalization, Request persistence, duplicate protection, error
translation, and mutation ordering.

The current provider implementation retains some `Jellyseerr` names for
compatibility with the established Atlas package and environment contracts.
Repository source now selects the pinned Seerr runtime, while the deployed
production container remains a separate migration and release-acceptance gate.

## Discovery Read Path

Atlas exposes read-only discovery/search through:

```text
GET /api/v1/media/search
GET /api/v1/media/discover
```

Discovery requires `media.read`. Results normalize provider data into the public
Media discovery contract used by `/portal/media`.

`request_eligible` is advisory presentation state, not mutation authorization.
Only provider state `not_tracked` is currently considered request-eligible.
Tracked/known states and unsupported states fail closed. A stale eligible card
may therefore still be rejected by the authoritative Request POST.

Provider media identity is carried internally so Atlas can address the intended
provider target. The Portal uses it for internal item identity and Request
transport, but B3.2/B3.3.2 do not render the raw identifier in Media cards.

## Request Mutation Path

Personal Request creation uses the self-scoped Request API:

```text
POST /api/v1/requests
```

The caller may provide only:

- `media_type`;
- `provider_media_id`;
- `title`;
- optional `year`; and
- optional `season_number`.

Atlas owns the authenticated user identity, provider selection, Atlas request
identity, provider request identity, lifecycle status, and timestamps.

Portal presentation additionally checks `requests.create` before showing the
movie Request control. The API enforces authorization independently; the Portal
permission check is never the security boundary.

The mutation sequence is:

```text
validate caller input
        |
        v
resolve provider + deterministic submission preflight
        |
        v
serialize active-target check + PENDING persistence
        |
        v
release Request registry lock
        |
        v
revalidate before SUBMITTING intent
        |
        v
persist SUBMITTING
        |
        v
provider defensive validation + external mutation
        |
        v
persist provider/result lifecycle state
```

Deterministic provider configuration errors therefore fail before a new Request
is persisted. Local persistence still precedes external mutation, while
outcome-ambiguous provider operations remain reconciliation-required.

## Active-Target Identity

An active Request conflict is global across Atlas users because Media provider
mutation uses shared server-side provider identity. The conflict identity does
not include user ID, title, or year.

The logical target is based on:

- provider;
- provider media identity;
- normalized media family; and
- TV season overlap where applicable.

For the Seerr-compatible provider boundary:

- movie and anime-movie normalize to the movie family;
- TV and anime-TV normalize to the TV family;
- all-seasons TV overlaps every explicit season;
- the same explicit TV season conflicts; and
- different explicit TV seasons may coexist.

Only active requests block creation. Terminal AVAILABLE, REJECTED, FAILED, and
CANCELLED history does not permanently prevent a later request.

## Inter-Process Registry Locking

The Request state directory contains:

```text
requests.json
requests.lock
```

`requests.lock` is persistent coordination state. Repository mutations acquire a
Linux `fcntl.flock()` exclusive lock around the complete read-modify-write
transaction. Initialization, generic save, strict active-target save, replace,
and delete all participate in the same process-shared lock boundary.

Reads remain lock-free because `requests.json` is published through atomic file
replacement. Every process that writes Request state must use the repository
mutation boundary and the same Request-state filesystem.

A process crash releases the kernel lock when its descriptor closes; the
persistent sidecar does not require stale-PID cleanup.

## Duplicate and Concurrency Behavior

The strict creation path performs the active-target check and initial `PENDING`
write while holding one exclusive lock. Once the first creator persists
`PENDING`, a second creator sees an active conflict even if the first creator has
not yet advanced to `SUBMITTING`.

The losing caller receives the existing HTTP 409 conflict path and cannot reach
a second provider submission.

The repository's generic `save()` remains permissive for controlled fixtures,
imports, migrations, and explicit lower-level use; normal Request creation uses
the strict active-conflict path.

## Interrupted and Ambiguous Provider Mutations

Duplicate protection does not replace Interrupted-Request Recovery. Atlas still
persists `SUBMITTING` or `CANCELLING` mutation intent before the corresponding
provider operation. If the provider outcome is ambiguous, Atlas retains a
recovery-required active state and instructs the caller not to retry blindly.

The Portal create transport uses zero automatic retries. After any movie Request
attempt, the target remains locally blocked for the lifetime of that page:

- success -> `Requested`;
- stale active-target 409 -> `Already requested`;
- reconciliation-required or otherwise unconfirmed outcome -> `Check requests`.

This browser-level block improves user experience but does not replace the
server-side active-target invariant.

## Current Portal Mutation Scope

B3.3.2 enables movie Request mutation only. Eligible TV cards do not POST a
request. The Portal instead explains that explicit season selection is required.

This is deliberate. At the current provider boundary, `season_number=None` for
TV means all seasons. Atlas must not silently convert a generic series-card click
into that scope.

Server-side TV and anime-TV Request capability remains intact and is the
foundation for the later Portal season-selection workflow.

## Ongoing TV and Anime Series

Ongoing-series automation remains a v1.0 requirement. Once the supported
TV/anime Portal request workflow is enabled, the user should choose the intended
series/season scope once. The downstream Seerr/Sonarr or Seerr/Sonarr Anime
configuration is expected to keep the supported ongoing series monitored so
future episodes can be acquired automatically under the configured monitoring,
quality, and release rules.

Atlas should not require a new user Request for every future episode of an
already monitored ongoing series.

### Monitoring Ownership and Runtime Gate

Ongoing-series monitoring is owned by the configured Seerr Sonarr service, not
by caller-controlled Atlas Request fields. The target Seerr runtime exposes
`monitorNewItems` as a Sonarr-service setting and forwards that value when a new
series is added to Sonarr. Atlas therefore does not add a per-request
`monitorNewItems` field or allow the browser to control that downstream
monitoring policy.

The canonical repository runtime is pinned to Seerr v3.4.1. The production
container observed during B3.3.3C still used the legacy
`fallenbagel/jellyseerr:latest` lineage and exposed neither a
`monitorNewItems` setting on its two sanitized Sonarr service records nor
`monitorNewItems` support in its deployed application code. Source ownership and
production runtime state are therefore intentionally distinguished.

Before v1.0 series-request acceptance can pass, the controlled production
deployment must:

1. back up the existing Seerr/Jellyseerr configuration and preserve rollback;
2. migrate/recreate the service on the repository-pinned Seerr image;
3. verify the standard-TV route and anime-TV route still resolve to the intended
   Sonarr service IDs;
4. set and verify `monitorNewItems=all` for both supported Sonarr services; and
5. prove through production E2E validation that a newly requested ongoing
   standard series and anime series remain monitored for future episodes.

Season request scope and future-season monitoring are separate concepts. An
explicit season request still represents that Atlas Request's user-selected
season scope, while Seerr's service-level monitoring policy determines whether
Sonarr automatically monitors later seasons added to upstream metadata. The
Portal must not present service-level monitoring as a per-request toggle unless
Atlas later implements a separate authoritative downstream control.

This section defines the required end-user/operational acceptance target. It
does not claim that Portal TV/anime season selection or the production Seerr
migration is already complete.

## Security Properties

- Browser-to-Seerr access is prohibited.
- Provider credentials remain server-side.
- Raw provider request IDs remain server-private.
- Discovery uses `media.read`.
- Mutation uses `requests.create`.
- Request ownership is derived from the authenticated user.
- Caller-controlled POST fields cannot set lifecycle/server-owned state.
- Active-target uniqueness is server-authoritative.
- Provider submission happens only after local persistence.
- Automatic mutation retry is disabled in the Portal transport.
- Reconciliation-required state fails closed.

See [Security](SECURITY.md) for the broader trust-boundary model.

## Related Architecture

- [Interrupted-Request Recovery](INTERRUPTED_REQUEST_RECOVERY.md)
- [Security](SECURITY.md)
- [Portal](PORTAL.md)
- [Unavailable-Provider Behavior](UNAVAILABLE_PROVIDER_BEHAVIOR.md)
- [Storage Exhaustion Recovery](STORAGE_EXHAUSTION.md)
- [ADR 0016 — Interrupted-Request Recovery Boundaries](../ADR/0016-interrupted-request-recovery-boundaries.md)

## Validation Boundary

The B3 source chain was validated incrementally and then through full regression
gates. The final server-side race-protection gate passed 3,055 Core tests plus
104 subtests and 336 API tests plus 15 subtests. The final Portal action gate
passed the full 194-test Portal suite, typecheck, lint, and production build.

Production deployment, explicit TV/anime season-selection UX, ongoing-series
runtime acceptance, end-to-end journey certification, accessibility,
performance, sustained-use, pilot, stabilization, and v1.0 release approval
remain separate gates.
