# Source generation and held rollout journal integration

The generation adapter connects actual no-replace source publication and retained
rollback to the component rollout journal. Other surfaces remain delegated to an
explicit runtime adapter. Docker/systemd production actions are still pending;
there is no public dispatcher or activation command in this change.

A journal completion is preceded by optional adapter confirmation, then exact
identity and protected-context checks. Existing single-action fixture adapters
remain compatible. The generation adapter requires confirmation for its delegated
runtime surfaces. A production coordinator must select the intended adapter; it
must never substitute the fixture adapter.

Confirmation repeats idempotent generation flushes when adopting a source rename
whose intent survived a crash. It does not repeat component replacement. An fsync
failure retains the pending intent. Explicit resume must complete confirmation
before recording a completion, including when changing direction to rollback.

Rollback stops/restores runtime surfaces in reverse order before moving source to
source-retained. Its inactive guard must prove no container or service refers to
the source. This stage tests that contract with private fixtures; it does not prove
production inactivity or operational restoration. Original owner, maintenance,
current pointer, candidate and failed-transaction evidence remain unchanged.
