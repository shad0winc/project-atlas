# Original owner preservation prerequisite

This host-only source component creates an immutable owner-preservation.json under
an existing held publication journal. No production command or dispatcher calls
it yet. It does not move/archive/unlink a lock, clear a marker, or reopen ingress.

Preparation requires the inherited exclusive native flock, original owner and
publication intent, published current record/generation, exact structural held
boundary, and a fresh hash-pinned private acceptance receipt revalidated against
current canonical source, runtime and provider state. The executing plan collector
must match its tracked canonical source bytes. It requires the lock directory to
contain exactly one regular, singly linked owner file. It records directory and
file identity, ownership, modes and owner content hash, plus the exact receipt,
context, intent, current and held-boundary hashes.

The only proposed destination is the publication journal's original-update.lock.
Any eventual archival implementation must rename the complete original directory
on the same filesystem and flush both parent namespaces. Copying the owner and
then deleting its original would lose the original inode/ownership history and
is not this protocol. This stage performs neither operation.

Every plan explicitly denies owner release, ordinary reopening, CI acceptance and
public acceptance. It is a preservation prerequisite, not a release certificate.
Future CI/public evidence binding and an authorized resumable archive/completion
driver are still required; the ordinary deleting release helper is not used.

Matching retries revalidate fresh acceptance and flush identical plan bytes. A
foreign or partial plan is retained and refused. Changed owner inventory, modes,
source, receipt, runtime, provider usability, or expired acceptance refuses the
preparation. Failures and abrupt exit leave the original owner, publication fence,
maintenance, prior baseline, failed transaction and linked journals intact.

Tests use real temporary Git sources, inherited flock, journal/record/generation
and immutable private receipts. External Docker and health gates remain fixtures.
They exercise plan durability, process death, retry/conflict, extra lock entries,
changed owner/mode, receipt expiry, held-boundary absence, runtime drift and wrong
exclusion. They do not establish production acceptance or archive/release safety.
