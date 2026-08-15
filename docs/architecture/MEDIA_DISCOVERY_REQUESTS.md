# Media Discovery and Request Safety

## Purpose

This document defines the implemented Atlas boundary for Media discovery,
Personal Request creation, duplicate/race protection, and Portal request
presentation through M-023.27.3B3.

The design keeps provider-specific discovery and mutation behind Atlas. Browser
clients consume normalized Atlas contracts and never become trusted provider
clients.

## Current Source Checkpoint

The B3 implementation is represented by eight atomic source commits:

- `755409de` — Seerr-backed Media discovery foundation;
- `7bd4a14a` — Personal Media browse/search Portal;
- `28cbb790` — active Request uniqueness and race protection;
- `b1c2ebcb` — movie Request action in the Portal;
- `b901702d` — TV-series detail and season metadata;
- `c1bbe9d5` — explicit TV/anime-TV routing and submission preflight;
- `10c57e67` — fail-closed per-season requestability; and
- `ad84a30d` — explicit one-season TV/anime Request actions in the Portal.

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
Repository source and the deployed production service now use the
repository-pinned Seerr runtime. E2.5 completed the controlled production
migration and revalidated the server-owned standard-TV and anime-TV routes.

## Discovery Read Path

Atlas exposes read-only discovery/search through:

```text
GET /api/v1/media/search
GET /api/v1/media/discover
```

Discovery requires `media.read`. Results normalize provider data into the public
Media discovery contract used by `/portal/media`.

Whole-item discovery `request_eligible` is advisory presentation state, not
mutation authorization. Only provider state `not_tracked` is considered
whole-item request-eligible. Tracked/known states and unsupported states fail
closed, and a stale eligible card may still be rejected by the authoritative
Request POST.

TV-series detail is read through:

```text
GET /api/v1/media/tv/{provider_media_id}
```

Each normal non-Specials season carries normalized `availability`,
`requestability_known`, and `request_eligible`. A completely untracked series
marks its normal seasons as known and requestable. For tracked series, Atlas
uses the pinned-Seerr nested season/request evidence when that evidence is
present and valid. Pending, approved, and failed standard provider requests
block their explicit seasons; declined, completed, and 4K provider requests do
not block the standard season path. A season is eligible only when its normalized
provider state is `unknown` or `deleted` and no blocking request occupies it.
Missing, malformed, duplicate, or unsupported nested provider evidence fails
closed to unknown requestability and no Portal mutation action.

Provider media identity is carried internally so Atlas can address the intended
provider target. The Portal uses it for internal item identity and Request
transport but does not render the raw identifier in Media cards.

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

Portal presentation additionally checks `requests.create` before showing movie
or explicit-season TV/anime Request controls. The API enforces authorization
independently; the Portal permission check is never the security boundary.

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

The Portal create transport uses zero automatic retries. After any Portal
Request attempt, the logical target remains locally blocked for the lifetime of
that page:

- success -> `Requested`;
- stale active-target 409 -> `Already requested`;
- reconciliation-required or otherwise unconfirmed outcome -> `Check requests`.

For TV/anime, the page-lifetime target key includes the explicit season scope so
different requestable seasons can remain independently actionable while the same
season cannot be blindly replayed. This browser-level block improves user
experience but does not replace the server-side active-target invariant.

## Current Portal Mutation Scope

The Portal supports movie mutation and explicit one-season TV/anime mutation.
TV cards first load Atlas TV-series detail and display normalized season state,
including for tracked or partially available series. A season Request action is
shown only when that season has known, eligible requestability.

Every Portal TV/anime mutation carries a positive explicit `season_number`.
`season_number=None` continues to mean all seasons at the provider boundary, so
the Portal does not expose a generic TV Request, an all-seasons shortcut, or a
current-season inference. Specials (`season 0`) remain outside normal selection.

The browser derives `tv` versus `anime_tv` only from the server-provided series
classification. It does not infer anime from title/genre data and does not
supply downstream `serverId` routing.

## Ongoing TV and Anime Series

Ongoing-series automation is a v1.0 requirement. The source-level TV/anime
Portal workflow lets the user choose one explicit positive season scope, while
the downstream Seerr/Sonarr service configuration remains responsible for
future-series monitoring.

E2.5 completed the controlled production migration to the repository-pinned
Seerr runtime and certified the production routing boundary:

- standard TV remains server-owned on Seerr server `0`;
- anime TV uses `media_type=anime_tv` and Seerr server `1`;
- server `1` resolves to `sonarr-anime`;
- the Anime library root is `/media/Anime TV`; and
- `monitorNewItems=all` is a service-level policy for the supported Sonarr
  services, not caller-controlled Request state.

Production acceptance used explicit-season requests and preserved the
distinction between Request scope and future monitoring. The successful
Anime-TV acceptance requested Demon Slayer: Kimetsu no Yaiba Season 2. Seerr
recorded only season `2`, Anime Sonarr created the series as
`seriesType=anime`, Season 2 remained monitored, and standard Sonarr had zero
matching targets after submission.

The first Anime acceptance candidate, Mushoku Tensei: Jobless Reincarnation,
exposed a harness/discriminator misroute. That attempt failed closed and was
reconciled without media loss; it is recovery evidence rather than the passing
Anime-TV case.

Season request scope and future-season monitoring remain separate concepts. An
explicit season request represents the authenticated user's Atlas Request
scope. Seerr's service-level monitoring policy determines whether downstream
Sonarr continues monitoring future upstream metadata. The Portal does not
expose `serverId`, `monitorNewItems`, generic TV, all-seasons shortcuts, or
browser-inferred anime routing.

E2.5 therefore closes the production Seerr migration, TV/anime route
verification, service-level monitoring verification, and ongoing-series
production acceptance gates. End-to-end journey breadth, accessibility,
performance, sustained-use, pilot, stabilization, and final v1.0 approval
remain separate release gates.

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
gates. D1 passed 3,106 Core tests plus 104 subtests and 348 API tests plus 15
subtests after adding fail-closed per-season requestability. D2 passed 26 focused
API tests plus 3 subtests, 60 focused Portal tests, the full 211-test Portal
suite, typecheck, lint, and production build while adding explicit one-season
TV/anime mutation.

Production deployment, Seerr migration, `monitorNewItems=all` verification,
and ongoing-series TV/anime runtime acceptance passed under E2.5. Broader
end-to-end journey certification, accessibility, performance, sustained-use,
pilot, stabilization, and final v1.0 release approval remain separate gates.
