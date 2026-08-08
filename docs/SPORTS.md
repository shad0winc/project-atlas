# Project Atlas Sports Module

The Sports Module is an optional Project Atlas module for sports discovery,
subscriptions, scheduled recording, health, and maintenance workflows.

## Status

Current status: Operational backend foundation; v1.0 Portal experience in
progress.

The production Sports feed and controller services are deployed and healthy.
The provider, subscription, lifecycle, recording, scheduler, maintenance,
health, and recorder-recovery foundations are implemented. User-facing Sports
Portal and administration workflows remain tracked separately in `ROADMAP.md`.

## Design Goals

- Optional and independently manageable.
- Isolated from the core Media platform.
- Compatible with the Atlas module and scheduler frameworks.
- Safe to disable without changing core Media behavior.
- Observable before automated action.
- Fail closed when recorder process ownership is ambiguous.

## Runtime Services

The module currently deploys:

- `atlas-sports-feed` — Nginx-based Sports feed and health presentation;
- `atlas-sports-controller` — provider discovery, subscriptions, lifecycle,
  recording orchestration, health, and maintenance integration.

The feed exposes its health contract on port `8097`.

## Implemented Backend Capabilities

- Sports provider framework with TheSportsDB adapter.
- Event, team, and league subscription resolution.
- Provider degradation and recovery observations.
- Normalized Sports lifecycle processing.
- Scheduled recording planning with preroll and postroll support.
- FFmpeg recorder execution and exit-code sidecars.
- Partial recording finalization and terminal state persistence.
- Shared-scheduler maintenance integration.
- Bounded artifact and recording-metadata maintenance.
- Structured controller, provider, recorder, recording, and storage health.
- Recorder recovery using verified PID and Linux process start-time identity.

## Recovery Safety

M-023.19 hardened recorder recovery so PID liveness alone is never considered
proof of process ownership. Atlas persists the process start-time token and
requires PID plus start-time identity before adopting or signaling an existing
recorder.

Missing or mismatched identity fails closed. An unrelated process with a reused
PID is neither adopted nor signaled.

See:

- [Sports Recovery Architecture](architecture/SPORTS_RECOVERY.md)
- [ADR 0017 — Sports Recorder Process Identity](ADR/0017-sports-recorder-process-identity.md)

## Storage

```text
/mnt/storage/media/Sports
/mnt/storage/configs/sportyfin
├── input
├── output
├── logs
├── recordings
└── state
```

The module also uses the shared Atlas scheduler runtime beneath
`/mnt/storage/configs/atlas/runtime`.

## Remaining v1.0 Experience Work

The backend foundation must not be confused with a completed friend/family
Sports experience. Remaining work is tracked in `ROADMAP.md` and includes the
supported Portal experience for browsing and requesting events, viewing
recording status and completed recordings, favorites/following workflows,
playback handoff, administration, and user-friendly failure presentation.

## Module Reference

Operational module details, registered commands, and implementation layout are
documented in [`modules/sports/README.md`](../modules/sports/README.md).
