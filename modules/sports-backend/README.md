# Project Atlas Sports Backend

The Sports Backend module provides private infrastructure used by Atlas Sports.

It currently contains:

- Dispatcharr for authorized stream/channel aggregation and normalization.
- Teamarr for sports-event-to-channel orchestration and EPG integration.

## Trust Boundary

These services are backend infrastructure only.

Atlas remains authoritative for:

- Atlas user identity;
- per-user Sports follows;
- per-user recording intent;
- notifications;
- live-session admission and concurrency;
- Theater access.

Atlas users are not provisioned into Teamarr or Dispatcharr.

Jellyfin remains the per-user playback/transcoding backend linked to Atlas users.

## Network

Both backend services use only the private Docker `atlas` network.

No host ports or Atlas public ingress routes are declared.

## State

Persistent state:

- `/mnt/storage/configs/dispatcharr`
- `/mnt/storage/configs/teamarr`

The directories may contain sensitive third-party application state and must not
be dumped into diagnostics.

## Deployment

Images are pinned by immutable OCI digest.

Installation creates persistent state directories, prepares a private module
`.env`, pulls only the pinned images, starts the two containers, and verifies
the resulting private runtime.

Uninstall stops/removes containers but deliberately preserves persistent state.

## Cutover

Installing this module does not configure:

- Jellyfin Live TV;
- Teamarr -> Dispatcharr integration;
- upstream IPTV/M3U sources;
- Atlas Watch Live bindings;
- Sports recording cutover.

Those are separate, evidence-gated changes.

## Dispatcharr state ownership

The pinned Dispatcharr AIO image defaults its application identity to UID/GID
`1000:1000`. Atlas therefore ensures that the bind-mounted Dispatcharr state
root is owned by `1000:1000` before first startup.

Atlas changes only the root ownership. Dispatcharr remains responsible for
ownership and permissions below `/data`, including its PostgreSQL data
directory.

Dispatcharr may add execute permission to the `/data` root during startup.
Verification therefore enforces the security properties of the directory
rather than one exact mode: the owner must have read/write/execute access and
group/other must not have write access.

## Dispatcharr HEAD compatibility

The Atlas Dispatcharr derivative uses the same immutable upstream digest. Its
hash-guarded patch permits HEAD on the TS stream route after the existing network
access check and channel/stream identity lookup. HEAD returns MPEG-TS headers and
an empty streaming response, without creating a proxy, selecting an upstream,
registering a viewer, reserving capacity, or changing Redis accounting. It does
not assert that the upstream feed is on air. GET behavior is preserved.

The image build runs the real Django REST Framework method contract with
synthetic settings and fenced upstream operations. A changed upstream source
hash stops the build. The separate native generation-authority patch workspace
is not included in this derivative.
