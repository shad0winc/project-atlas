# Held publication coordinator

This internal host operation consumes an already prepared PublicationIntentJournal
under the original owner's inherited exclusive flock. It is not exposed through
`atlas deployment` and is not a production deployment instruction. Source must
pass the native clean-main guard, the executing module must be from that canonical
checkout, and a redirected deployment namespace is refused. Exact tested source
and CI evidence must also be pinned by the future deployment driver.

Before current advances, fresh runtime, Doctor and Verify gates run on the pinned
prepared candidate. A separate record copies the exact candidate files, retains
metadata and archives, changes only status to verified and reseals the manifest.
Metadata must identify that publication as a baseline following the pinned old
baseline. Staging files/directories are flushed before rename; both containing
namespaces are flushed afterwards. An existing target or stage is adopted only
if its complete inventory and bytes match. Partial/foreign objects are retained
and refused, never overwritten or silently discarded.

Native runtime verification runs on the published record. The existing native
set-current path enforces mixed provenance, materializes/flushed scheduler source
and durably replaces current. Fresh post-pointer runtime, Doctor and Verify must
pass before a held-boundary observation is recorded. A failure after current
advances retains current and all evidence; it never tries an uninformed rollback.

Explicit resume accepts only the original current or exact intended target. The
latter requires exact record inventory, a matching record observation and scheduler
generation identity markers, followed by fresh native runtime/Doctor/Verify gates.
Generation markers are structural restart observations, not substitutes for full
native source/blob/config validation. A complete immutable record staging directory
left by process death can be adopted and flushed; partial staging requires review.

Original owner bytes/inode/permissions and publication-pending remain required
through every operation. No release, archive, maintenance disable or marker-clear
operation is provided. Generic repair cannot open admission. Held-boundary.json
explicitly denies reopening and is not a private or public acceptance certificate.

Validation uses disposable state and real archive/current publication. Only the
external runtime/Doctor/Verify gates are fixtures. Tests establish control flow,
refusal and process-death behavior, not production health, physical power loss,
real decoder/encoder behavior or operational backup restoration.

Still required before production use: exact canonical commit/CI evidence and fresh
acceptance receipt binding, provenance/recovery recipes for the new API/Caddy/host
service, owner archival/release and completion protocol, complete release checks,
protected source promotion and controlled live private/public acceptance. The
older immutable prepared candidate remains untouched and must not be used for
the expanded runtime without a separately reviewed new provenance record.
