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
