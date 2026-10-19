# Full Core maintenance validation corrections

The first accumulated maintenance Core run stopped with 34 failures, 5,718 passes,
12 skips and 1,761 passing subtests. The source, production runtime, maintenance,
original owner, candidate and prior recovery evidence were preserved. The failed
receipt and full log remain immutable historical evidence.

The correction scope is test isolation and a private restore rehearsal adapter:

- Bootstrap-order assertions now locate the transaction-aware maintenance enable
  boundary, preserving the requirement that bootstrap precedes maintenance/backup.
- Failed-before-apply source inspection stops at its own next shell function,
  excluding unrelated held-publication helpers appended later in the same file.
- Two provisioning worker cases pass their own empty live-source registry, so
  no production catalog is consulted before the intended resolution/failure check.
- Restore/metadata test stages use explicit private /tmp directories required by
  the existing native isolation guard, independently of the runner's TMPDIR.
- The private maintenance rehearsal lets the real abort wrapper acquire exclusion
  once. Its RPC adapter now implements verify-held completion, checks two runtime
  boundaries while maintenance remains enabled, and forbids a disable call.
  Success still releases only the disposable rehearsal owner after all checks;
  failure retains it. The real production restore controller is unchanged.

The targeted runner validates affected modules and installs only this reviewed
scope into the isolated feature checkout if all checks pass. It does not loosen
production permissions, use global Git trust, change native /tmp guards, read live
Sports catalogs for tests, activate services, reopen ingress, or release the
original production lock. A new full Core pass and remaining release checks are
still required for the corrected source tree.
