# Atlas Sports Module

The Sports Module is the optional Project Atlas runtime for sports discovery,
subscriptions, scheduled recordings, health, and maintenance.

## Status

Operational backend foundation. The production feed and controller services are
deployed and healthy. Friend/family Portal and administrator Sports workflows
remain v1.0 product work and are tracked in `ROADMAP.md`.

## Runtime Services

- `atlas-sports-feed`
- `atlas-sports-controller`

The module depends on the Atlas network and declares Jellyfin as its core
service dependency. The feed health surface is available through port `8097`.

## Implemented Components

- provider abstraction and TheSportsDB provider;
- event/team/league subscriptions and resolution;
- lifecycle and controller processing;
- feed generation;
- FFmpeg recording and recording-state persistence;
- exit-code sidecars and partial-file finalization;
- scheduler integration;
- maintenance and retention of Sports artifacts;
- structured health; and
- fail-closed recorder recovery using PID plus Linux process start-time
  identity.

## Registered Module Commands

The module registers commands for:

- `follow-event`
- `follow-league`
- `follow-team`
- `maintenance`
- `search`
- `subscribe`
- `subscriptions`
- `unsubscribe`
- `upcoming`

The exact dispatch contract is defined by `commands.json`.

## Scheduled Work

`scheduler.json` registers the Sports maintenance task with the shared Atlas
scheduler. Sports does not implement a parallel scheduler.

## Persistent Paths

```text
/mnt/storage/configs/sportyfin
├── input
├── output
├── logs
├── recordings
└── state

/mnt/storage/media/Sports
```

Shared scheduler state is stored under `/mnt/storage/configs/atlas/runtime`.

## Recovery

Recorder identity is not PID-only. New active recorder state persists:

- `pid`; and
- `process_start_time`, the Linux procfs process start-time token.

Adoption and termination require verified identity. Missing or mismatched
identity fails closed so an unrelated process is never adopted or signaled
solely because its PID matches old state.

See:

- `../../docs/architecture/SPORTS_RECOVERY.md`
- `../../docs/ADR/0017-sports-recorder-process-identity.md`

## Verification

Sports integration coverage includes provider, recording, recovery, scheduler,
and maintenance suites. The repository-level Atlas test command remains the
supported entry point for module test execution.

## Scope Boundary

This module provides the Sports backend foundation. The complete v1.0 Portal
experience, supported playback experience, request administration, favorites,
and user-facing failure handling are not claimed complete by this document.
