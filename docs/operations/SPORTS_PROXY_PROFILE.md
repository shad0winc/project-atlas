# Sports Proxy profile binding

Automatic Sports channel provisioning requires ATLAS_DISPATCHARR_PROXY_PROFILE_ID.
Before deployment, verify the configured positive integer identifies the installed
Dispatcharr TS Proxy profile (not Redirect or an FFmpeg profile). IDs are installation
specific; the observed Project Atlas installation currently uses profile 3.

The controller Compose environment forwards the setting. Missing or invalid values
stop reconciliation before channel mutation. Creation and updates explicitly set
stream_profile_id, retaining the requested stream order and binding identity.
An existing working channel is not changed by this source PR.

Deploy through the scoped deployment workflow with the verified profile setting,
retained parent runtime, rollback evidence, and admin-only maintenance. Source merge
alone does not activate this change. The numeric setting does not itself attest
profile semantics: that check remains a deployment prerequisite.

This fixes output profile selection only. It does not publish backup playback
options, prove provider independence, or claim physical sharing/failover acceptance.

## Deployment checkpoint, 2026-11-04

The controller-only rollout published `baseline-sports-proxy-profile-7455a793428d`
from main commit `7455a793428da34cb4eee3ca5532e12f87e27063` (PR #445).
The previous publication was `baseline-caption-startup-b092b54dc97b-bolr3ked`.
Activation completed with maintenance retained. The operator verified that
an administrator could access the maintenance console and a regular user
was denied. Private live playback acceptance was still pending.

An earlier activation attempt rolled back after the replacement controller
failed readiness. The staged source directories were accessible only to root,
while the controller runs as `atlas`. After restoring directory traversal,
an isolated container running as `atlas` verified all 38 pinned source files.
The fresh activation then completed.

## Distinguishing recovery from playback acceptance

- The Proxmox reboot check showed the media pool ready before CT100 startup.
  The storage watcher reported healthy, Docker started, and the API became
  healthy. Keep the storage latch as a fail-closed guard.
- The Sports writer resumed provider fetches after a recorded refresh failure.
  A separate Premier League cache read confirmed complete coverage and zero
  events for Nov. 4 Eastern, and the portal showed the empty schedule.
  One recovery does not establish sustained freshness across competitions.
- Check the writer's authenticated `/internal/v1/metadata/refresh-status`
  alongside the affected competition's curated schedule snapshot. A recent
  provider success can belong to a different competition. Compare the
  snapshot status, observation time, coverage, and expiration.
- Use an isolated fixture to rehearse transient failures and verify recovery.
  Keep provider refresh checks separate from storage latch and deployment
  recovery drills. Do not reset a production latch or restart the writer to
  force a failure during live acceptance.
- For private acceptance, use a mapped live event with **Watch Live**, verify
  the provisioned or reconciled channel uses the verified Proxy profile,
  play for at least one minute, and confirm the session releases afterward.
  A scheduled event or successful follow alone does not establish playback.
