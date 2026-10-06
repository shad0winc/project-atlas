# Administration automation health

Administration exposes a read-only health panel under the existing `system.health.read` permission. Its authenticated GET endpoint is `/api/v1/admin/automation-health`. Refresh rereads observations; it does not reconcile, submit, migrate, clear or reset anything.

The panel reports recovery/routing flags from the current API process, structural request-registry observations and aggregate submission counts. Unresolved means POST_STARTED or RECEIPT_OBSERVED; an observed receipt has not yet been bound. Pending event counts exclude delivered outbox entries. These counts do not establish semantic validity or successful recovery. Schema 1 does not report invented empty recovery journals.

Scheduled reconciliation comes from the existing API-safe scheduler snapshot, never from a TaskScheduler instance. Both snapshot generation and last-success age must be within five minutes for a healthy observation. Failed/disabled tasks or consecutive failures require attention. Missing, malformed, ambiguous, future-dated, oversized or unreadable observations are unavailable. A stale snapshot cannot prove the current timer is active. API flags do not prove scheduler flags match.

Readers open regular files without following final-component symlinks, bound reads to 8 MiB, and suppress private error details. Responses omit request IDs, users, titles, receipt IDs, credentials, URLs, file paths and raw scheduler errors. GET performs no file creation, state cleanup, provider calls, stream actions or Docker/systemd actions. Existing runtime mounts and permissions remain in place.

An enabled flag or a healthy scheduled pass is not acceptance evidence for new/uncertain receipt recovery, acquisition/import/audio/subtitle behavior, or physical upstream sharing and viewer stop isolation. Native receipt validation and deployment generation still require the guarded operator workflow; this panel does not publish private installation journals or claim those checks occurred.

Manual recovery actions remain outside this change. Any later action must persist intent, check exact identity and ownership, reconcile uncertain outcomes, and audit the action. A generic reset that deletes submissions, outboxes, sessions, leases or locks would violate Atlas fundamentals.

Validate full API regression, Portal tests, typecheck and changed-file lint in an isolated worktree. Commit exact paths, require all six exact-head CI checks, merge matching head and deploy through the supported Ingress transaction. After deployment, check authorized/denied visibility and refresh while routing stays disabled. This review packet does not deploy or activate anything.
