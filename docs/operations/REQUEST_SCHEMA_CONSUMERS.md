# Request schema consumer compatibility

The API, scheduled request service and recovery-state validator use
`atlas.media_requests.construction.open_request_repository` to select the
persisted request contract. Missing registries continue to use schema 1.
Existing schema-1 registries use the legacy service. Explicitly migrated
schema-2 registries use `SubmissionRecoveryRepository` and
`SubmissionRecoveryService`. Construction does not initialize, migrate or
rewrite the registry, allocate profiles or make provider calls.

Malformed, unsupported, non-integer, symlink or non-regular registry contracts
fail closed. Schema 1 cannot contain recovery journal fields. Schema-2 journal
shape is checked before exposing its consumer. API construction failures use
the existing unavailable boundary.

This compatibility change does not configure acquisition profile/server maps,
schedule receipt reconciliation or drain submission outboxes. It does not
establish downstream deduplication, native correlation after uncertain POSTs,
all-season support or imported language/subtitle evidence. Existing readiness
and unknown-outcome barriers remain in place.

Do not migrate production merely because these consumers are compatible.
Migration remains a separate operation after all writers/readers and recovery
tools use compatible deployed generations, routing/profile identities are
verified, bounded recovery and event delivery are wired and tested, and private
backup/recovery is reviewed. Pause all request readers/writers for migration.
Never restore a pre-attempt registry over an active submission journal.

A long-lived consumer selected before a schema change rejects the changed
schema on access. Restart compatible processes during the separately reviewed
activation. No implicit downgrade or registry repair is provided.
