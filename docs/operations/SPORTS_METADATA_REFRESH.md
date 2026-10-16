# Sports metadata automatic refresh

Status: optional source integration, disabled in production. No policy, Compose
mount, environment credential, storage directory or provider registration is
installed by this change. SportsDB remains independently degraded when it fails;
this worker does not change doctor or provider-health.json.

## Explicit configuration

The private Sports writer owns the worker. Set an absolute
`ATLAS_SPORTS_METADATA_REFRESH_FILE` to a server-owned regular JSON file readable
by the writer, with no group/other write permissions. Owner must be root or the
writer UID. Symlinks, special files, duplicate JSON keys, unknown fields, unsupported
routes and oversized documents fail closed. Missing or exactly
`{"version":1,"enabled":false}` is disabled. Enabling an initially missing/disabled
policy requires writer restart; an existing worker rereads its policy every tick.

The state environment `ATLAS_SPORTS_METADATA_STATE_DIR` must point to an already
provisioned writer-owned private directory. The canonical host recovery path is
`/mnt/storage/configs/atlas/private/sports-metadata`; eventual container mapping
must select this exact supported host path. This candidate does not provision it.
The current Compose deployment has no corresponding mount or policy configuration.

This is a policy example for review, not an installed canary:

```json
{
  "version": 1,
  "enabled": true,
  "routes": ["football/nfl"],
  "hourly_budget": 96,
  "current_ttl": 60,
  "past_ttl": 3600,
  "future_ttl": 3600,
  "directory_ttl": 3600,
  "tick_seconds": 1,
  "generation": "review-required"
}
```

Each route needs today, yesterday and seven future scoreboard buckets. Non-UFC
routes also need a team directory. The policy loader checks the nominal hourly
rate: current-day refresh plus one past-day and seven future-day refreshes per
route, plus directory refresh. At the example TTLs, six routes require a nominal
413 requests/hour, so the NFL example's budget cannot silently enable all six.
These are Atlas request ceilings, not upstream quota guarantees. The broker's
persisted rolling attempt count and cooldown always arbitrate actual requests,
including interactive consumers, retries, cold starts and date rollovers.

## Lifecycle and observations

One due request is selected per tick. Today is prioritized, then missing directories
and date buckets; existing current data is never declared fresh merely because a
loop ran. Cold cache remains partial until observed buckets are available. Failure
and cooldown handling preserves last-known observations. There is no hot retry.
Deleting/disabling policy pauses subsequent requests after the current operation;
an invalid reload makes no new refresh requests. A policy edit affects future
operations; it cannot cancel an already admitted request.

Authenticated `/internal/v1/metadata/refresh-status` reports worker state, policy
fingerprint, last tick, last actual provider success and failure category/time.
Cache hits do not update provider-success time. This is neither a full-coverage
attestation nor global capability health. User-facing schedule results retain
explicit cache coverage and age through the existing schedule endpoint.

SIGTERM/SIGINT stop admissions, join refresh work within a 25-second budget and
close the server. Configure at least a 30-second container stop grace period
before enabling. Crash/forced stop still relies on persisted unknown-outcome
holds and request reservations. Maintenance at public ingress does not stop the
worker; consistent backup uses the shared lock and SQLite online backup.

## Remaining activation work

Production remains on the existing deployment. Before activation, install reviewed
private mounts/policy through canonical deployment, verify restore/rollback and
writer quiescence, wire independent discovery and cross-provider follow identities,
add truthful capability health, and complete production acceptance. No feed is
made playable by metadata; Jellyfin/Dispatcharr binding and session ownership
remain separate requirements. Wrestling and other fight promotions still need
separate fixture-backed coverage.
