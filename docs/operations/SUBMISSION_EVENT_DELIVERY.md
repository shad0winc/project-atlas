# Submission outbox journal delivery

The shared schema-2 request service factory supplies a dedicated submission event
publisher for API and Core consumers. Schema-1 behavior stays unchanged. This
change does not migrate the registry, schedule receipt recovery, change routing,
activate acquisition, or modify Sports admission or retention.

The outbox's `metadata.submission_event_id` is the logical identity. Publication
uses a deterministic outer journal ID, compares the complete persisted payload,
and fsyncs the journal before permitting acknowledgement. A complete matching
older API/Core record with a random outer ID is accepted after fsync. Replaying
publication after an acknowledgement failure does not append another record.
Concurrent submission publishers use a nonblocking exclusive inode lock; a
busy writer retains pending work for a later retry.

The existing private regular journal must be readable and writable by the
consumer. The configured `ATLAS_EVENT_LOG` must be absolute. Construction has no
journal I/O. The publisher never creates, rotates, repairs, truncates or clears
journal state. It accepts no world permission bits, symlinks, FIFO, incomplete
JSON tails, conflicting event identities or duplicate logical records. Record
size is bounded at 16 KiB and total scan/append size at 64 MiB. Publication fails
closed if these limits are reached; journal lifecycle planning remains required
before sustained schema-2 activation. An inode replacement observed during
publication also prevents acknowledgement. Generic legacy writers continue
their existing append behavior and do not participate in the submission lock.
Administrative journal replacement/truncation must be coordinated separately.

A failed write, fsync or acknowledgement leaves the outbox pending. A partial
tail or identity conflict requires read-only reconciliation first; do not
blindly replay, remove evidence or clear guards. A successful retry of a complete
record fsyncs it again before acknowledging. This is replay-safe logical journal
publication, not a promise of exactly-once delivery by external notification
adapters or their cursor processing. Explicit direct service callers may inject
a different publisher; their delivery guarantees remain their responsibility.

Focused tests cover real-file restart replay, legacy record compatibility,
identity conflicts, lock contention, concurrent retry, fsync failures, short
writes, malformed evidence, inode replacement, file permissions/types, bounds,
and the publish/acknowledge crash boundary using the real recovery repository.
API construction and scheduler compatibility are checked in the full CT100
checkout with its canonical virtualenv. No live provider is contacted by these
fixtures.
