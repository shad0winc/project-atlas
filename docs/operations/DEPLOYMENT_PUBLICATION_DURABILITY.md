# Native publication durability primitives

Status and current publication use a same-directory temporary file, complete
write, file fsync, destination identity recheck, atomic replacement, and parent
fsync. Existing file mode/ownership is retained; new files use mode 0644. Only
bounded ASCII identifiers and the status/current basenames are accepted. Unsafe
owners, group/world write access, hardlinks, symlink targets or symlinked parent
paths fail. The helper assumes the caller already holds native execution
exclusion; it is not a concurrency admission or compare-and-swap protocol.

Scheduler generation materialization retains native archive/link/provenance
checks. Before directory rename, regular files and directories are flushed from
leaves to root. The native root .env link may point only to the canonical
operator overlay and is persisted through directory fsync; the target is not
modified. After rename, destination and ancestor namespaces are flushed. Existing
generations undergo native archive identity checks and the same flush pass.

If file fsync fails before replacement, the previous pointer remains. A failure
or process death after replacement can expose the new complete value. Retrying
the same write is safe under caller exclusion, but failure does not establish
commit or acceptance. Maintenance and recovery ownership must remain held while
an operator determines which stage became visible. Temporary files left by
abrupt death are not acceptance records and are never adopted automatically.

The helper has no maintenance mutation, lock-release, record promotion, web or
socket endpoint. It cannot mark a deployment healthy or replace native runtime,
manifest, scheduler provenance, Doctor, Verify or controlled public acceptance.
The original recovery lock and failed records are outside its mutation surface.

Still required: a durable reconciliation journal binding old current, exact new
record/manifest, source generation and fresh acceptance; stable record publication
and restart classification; an original-owner preservation and release protocol;
and process-death tests of the fully integrated finalizer. Record-directory and
manifest durability are not completed by this primitive alone. Physical power
loss and restoration of the production backup have not been established.
