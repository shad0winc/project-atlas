# Publication-intent foundation

PublicationIntentJournal is a host-only preparation and inspection API. It borrows
the exact original transaction's open-description flock through the existing
TransactionMaintenanceAuthority. It requires an existing regular maintenance flag,
no incomplete control transition, and the exact baseline current file. It cannot
adopt another owner's descriptor or release any lock.

Before writing journal artifacts, begin validates the full flat candidate manifest
and inventory and the caller's protected evidence, including baseline and failed
record metadata/status. It creates and fsyncs publication-pending. Then it creates
and fsyncs a separate exact original-owner copy and immutable intent.json under
deployments/publication-journals/<publication-id>. Namespaces are flushed after
creation. The intent binds original directory/file device/inode, owner permissions,
owner bytes hash, current bytes hash, candidate inventory and supplied evidence.

The maintenance authority treats publication-pending as a pending hold for both
web and CLI. Its contents need not parse for admission to stay closed. A malformed
link also fails closed. Generic repair-hold forces maintenance on but does not
remove a publication marker. No socket operation can create, amend, commit or
clear publication intents.

Interruption before the journal completes leaves the marker and original owner
in place. A retry refuses partial evidence rather than truncating or replacing it.
A complete matching intent may be explicitly retried; its existing files and
namespaces are flushed again. Inspection rechecks exact current/owner/candidate
and protected evidence. Movement of current is reported as requiring review;
this foundation does not infer a successful commit or revert a pointer.

Tests cover actual inherited flock, failure to prove exclusion, unsafe candidate
inventory, protected-file changes, byte-identical owner replacement, source
mutation during journal creation, fsync failure and abrupt process death at all
three durable intent boundaries. The original current/owner and enabled flag
remain untouched. These syscall and process-death tests do not establish physical
power-loss behavior or operational backup restoration.

Still required: canonical native finalizer integration and durable record publish,
phase observations/restart classification after pointer movement, fresh private
and controlled public acceptance binding, a reviewed owner archival/release
protocol and explicit marker completion. Service provenance must first cover the
new API/Caddy and host authority. The older immutable prepared candidate is not
accepted or modified by this stage. This foundation provides no publication,
release or reopening authorization, and no production intent is created.
