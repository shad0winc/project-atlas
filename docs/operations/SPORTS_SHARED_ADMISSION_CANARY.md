# Sports shared-admission canary

Default: disabled. Missing configuration enables no sharing. No canary configuration
is installed by this review packet. Production shared admission remains disabled.

The API reads `/mnt/storage/configs/atlas/runtime/sports/shared-admission.json`.
The private Sports writer reads `/mnt/storage/configs/sportyfin/state/shared-admission.json`.
An explicit `ATLAS_SPORTS_SHARED_ADMISSION_FILE` override changes the respective
process's path. Both copies must contain identical configuration for admission to
succeed. Configuration is reread per admission; disabling or removing it blocks new
shared joins without a process restart. Cleanup does not depend on valid configuration.

Strict document fields: version (integer 1), enabled (boolean), mode ("canary"),
routes (at most one). An enabled document requires exactly one route. Route fields:

- target_id, resource_source_id: exact Atlas target and lifecycle resource.
- jellyfin_item_id: exact lowercase 32-hex publication binding.
- dispatcharr_channel_id, dispatcharr_stream_id, dispatcharr_account_id: native positive IDs.
- dispatcharr_channel_uuid: canonical UUID.
- capacity: integer 1; this canary cannot increase provider capacity.
- viewer_user_ids: exactly two distinct Atlas user IDs, not usernames.
- generation: explicit unique generation identifier.

Use a regular file readable by the service with no group/other write permission,
e.g. root-owned 0640 with a suitable read-only service group. Duplicate keys, unknown
fields, symlinks, special files, oversize files, invalid identities, and unsupported
modes fail closed. Fingerprints include all route fields, viewer identities and
generation; changing them cannot adopt an earlier shared allocation.

The authenticated private Sports writer endpoint `/internal/v1/shared-live-route`
accepts only an Atlas channel ID. It checks current catalog single-feed eligibility,
Dispatcharr publication and Jellyfin item bindings, lifecycle account identity and
capacity. It reuses the existing native verifier with token reuse/backoff to check
the actual channel's sole stream, stream account, staleness, account enablement,
credentials and native capacity. The primary source URL must match the exact internal
Dispatcharr channel path. A temporary in-memory option allows reuse of the verifier;
no option or feed is persisted or exposed in the UI. The endpoint returns only
logical target and configuration fingerprint. The API requires an exact matching
receipt before allocating shared capacity and keeps all per-user session checks.

This verifies routing metadata, not physical sharing. The allowlisted canary must
establish two independent authenticated Atlas/Jellyfin sessions, one real provider
connection, uninterrupted playback when either viewer stops, and cleanup after the
last viewer. Also test user limits, different-event capacity, unknown open/close
outcomes, crash/restart, and event rollover before general activation. The supported
mode is canary only; there is no production/global-sharing mode.

Do not adopt the currently playing exclusive lease. Begin a fresh generation only
after that viewer stops normally and owned/native cleanup is verified. All pool
readers must have schema-v2 compatibility before any canary writes schema-v2 state.
Rollback must preserve compatible readers for existing shared/held records; do not
remove reservations or downgrade their state to bypass reconciliation.

Dispatcharr can still see Jellyfin's backend client as anonymous. This change does
not provision downstream users or forward their identities. Backend profile linkage
is a separate unresolved contract; Atlas/Jellyfin ownership remains enforced here.
It also does not register backup feeds or prove three-feed availability.
