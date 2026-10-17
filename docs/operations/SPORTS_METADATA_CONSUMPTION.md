# Atlas metadata in strict native recovery rehearsal

This fixture-only extension replaces the two generic metadata/policy surfaces
in the strict native consumption rehearsal with the actual Atlas metadata
schema, identity registry and refresh-policy parser. It enables no worker,
network requests, live restore or deployment. Every identity and budget/cache
record is deliberately synthetic. No production database or policy is read.

Before journal exposure, the helper creates separate old and prepared metadata
stores through MetadataStore and MetadataIdentityRegistry. Their aliases,
cache observations, request-attempt rows and cooldown holds differ so rollback
can distinguish generations. Synthetic evidence hashes attest only the fixture
construction, not correspondence between real sporting events. A verified alias
cannot be reassigned within a store; fixture generations are separate databases.
The cache payload is a valid empty NFL scoreboard envelope with the expected
league UID, plus a synthetic generation marker. This does not attest real games,
coverage, freshness or provider availability.

The prepared current state then receives additional alias enrollment and
committed cache, budget-attempt and cooldown-hold changes through the real store
lock/transaction implementation, under the cooperative journal writer lease.
The budget/cache rows are seeded and committed as explicit fixtures; no HTTP
transport, broker request reservation or refresh scheduling is exercised.
The disabled policy changes byte formatting only. All three policy generations
must parse as disabled; the scheduler remains off and no policy is activated.

The existing strict PostgreSQL preparation still proves the dump marker
snapshot differs from the original stopped marker after-dump. Native database
commits, Docker stop/detach, stopped capture import and sealed native receipt
checks remain mandatory. The same five-surface journal then restores the old
metadata/policy alongside PostgreSQL, JWT and Teamarr, while retaining consumed
metadata/policy with the modified native state in quarantine.

Validation uses the actual recovery schema/alias validator and immutable SQLite
reads. It checks exact alias rows and provenance, cache payload/timestamps,
attempt rows and cooldown hold, plus exact disabled policy bytes. Unexpected
metadata sidecars, nonempty lock files, unsafe private metadata or extra policy
files hold the checks. Verification cannot silently initialize a missing schema
or change journal bytes.

## Numeric reader identity

After rollback, operator-private copies are materialized into fresh isolated
/tmp reader directories. Metadata receives UID/GID 1000:1000 with directories
0700 and files 0600. Policy receives UID/GID 0:1000, directory 0750 and file 0640.
The parent reader directory is root-owned 0750 with GID 1000. These assignments
apply only to the disposable copies, never the journal or production paths.

A fresh forked child drops supplementary groups and all real/effective/saved
user/group identities to numeric 1000. It validates metadata and policy through
read-only/immutable interfaces using code imported before the identity drop.
It starts no worker and makes no network calls. A bounded exit-code-only result
is returned; no database, JWT, policy or environment contents are printed.
Copied byte shapes must remain unchanged. This verifies kernel readability
under the planned identity, not a full Sports writer container startup.

Both restored-old and quarantined-consumed generations undergo that probe.
The metadata verification is repeated after the native applications complete
their restored startup and further persistence restart. Metadata itself is not
served by those applications; it is independently checked in the same combined
recovery sequence. Its writer/service integration remains a separate gate.

## Scope and verification

The existing native component gains an explicit complete metadata-hook set:
initialize, mutate and verify, permitted only with strict preparation enabled.
Defaults remain unchanged. The existing strict entry point's support pin is
updated for that backward-compatible component extension; its original source
checkpoint remains unchanged. The new metadata entry point pins all relevant
helpers, parsers/store sources and the modified component at the current source
checkpoint.

Run before committing in the new feature worktree:

```sh
git diff --check
python -B -m pytest -q tests/core
python -B scripts/diagnostics/sports-metadata-consumption-drill.py
```

Overall PASS requires the complete strict/native sequence, metadata and policy
checks, UID/GID 1000 reader probes, owned-resource cleanup and unchanged
production identity/mount observations, deployment pointer and clean canonical
checkout. A failed reader cannot be bypassed to print success. Local unit tests
exercise schema generations, byte preservation, alias conflicts, budget and
policy tampering, extra sidecars, journal exposure refusal and hook contracts.
The UID mapping tests defer only when the runtime cannot assign UID 1000;
CT100 must exercise the actual identity probe and real Docker rehearsal.

Applications still write disposable native volumes, not journal directories;
Teamarr still uses stopped grouped-sidecar capture and a detached snapshot.
Cross-application production backup coherence, direct native journal exposure,
authenticated business API UAT, live 16-surface orchestration and full Sports
writer/refresh activation remain separate gates. The controller requires
trusted serial operation. This is not a global Docker admission lock or
hardware power-loss certification. Existing live gates remain closed.
