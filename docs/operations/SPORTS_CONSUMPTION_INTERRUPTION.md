# Complete journal recovery under SIGKILL

This fixture-only extension tests interruption during recovery of the complete
strict-native and Atlas-metadata journal. It enables no live restore, deployment,
refresh worker or production state access. The original combined sequence still
creates a strict dump baseline, starts native applications, commits database and
metadata changes, stops/detaches the app objects, and imports stopped native
state before these cases begin.

## Recovery cases

The controller holds the source lifecycle, cooperative consumer and publication
locks while making private journal copies. It requires the source transaction
open, native import complete, no final seal, and both fixture app objects already
detached with retained volumes unreferenced. All five current surfaces and the
whole journal have bounded private byte hashes. One copy exists at a time.
Copies include the preserved old state, modified native cluster and snapshots,
real Atlas metadata schema, exact policy bytes, native import receipt and Docker
ledger. All copied contents and source hashes must match before each case.

Each case forks a private recovery worker. The selected existing durable
checkpoint sends SIGKILL to that worker's own PID. An ordinary exit, exception
or timeout cannot count as a successful interruption. The checkpoints are:

- sealing intent, seal document written and sealed status;
- rollback intent;
- quarantine of each of the five surfaces;
- old-state restoration of each of the five surfaces;
- final reverted status.

These are 15 recovery checkpoints, after completed setup/import. This does not
inject failure into every operation of dump preparation, application startup,
partial native import or baseline promotion. Those stages retain their separate
hold/retry tests. SIGKILL at durable software checkpoints is not a storage-device
power-loss test or a crash at every possible write/fsync instruction.

After every worker death, the parent requires exit status -SIGKILL and runs
native recovery twice on that copy. The original Docker identity and volume
fence remains mandatory for every recovery call. It verifies exact old hashes
in all five current surfaces, exact modified hashes in quarantine and empty
old/incoming directories. The actual Atlas schema, aliases, cache records,
budget attempts, cooldown hold and disabled policy bytes must validate in both
restored and consumed generations. The copy is then deleted, and the entire
source journal must still match its original hash before the next case.

A private INTERRUPTION.json audit is written only after all cases pass. It binds
the original source hash and exact checkpoint list. An existing audit is held,
not silently overwritten or used to skip cases. The original journal is then
recovered twice and checked identically. The combined controller continues with
its numeric UID/GID 1000 metadata/policy reader checks and both restored native
application starts. The native applications restart from the original recovered
journal after all cases; they do not restart separately for every copy. Each
copy's native baseline equality is proven by exact file hashes instead.

## Boundaries

The source remains unchanged through the independent cases; its intentional
recovery occurs afterward. Old/modified native state remains synthetic and is
copied only after application detachment. Applications write disposable native
volumes, not journal directories. The native import and ownership conversion
rules are unchanged. Metadata/policy use the actual schema and parser, with
synthetic identities and records. Policy stays disabled and no network request,
broker request reservation or full Sports writer startup is introduced.

The existing native component gains an optional recovery callback, permitted
only with the complete metadata extension. Its defaults stay unchanged. Support
pins in the older strict and metadata diagnostics are updated for that compatible
extension; their historical source checkpoints stay unchanged. The new entry
point pins all used support sources at the current reviewed source checkpoint.

Private journals have the existing entry/byte bounds. Whole-copy validation
requires the complete journal to fit the 2 GiB bound, not only each individual
surface. Copies run serially and are removed after each case. A worker deadline
is a failure, with the owned worker killed/reaped before cleanup. No native or
production process is selected by the SIGKILL operation.

The trusted serial controller excludes arbitrary concurrent privileged actors;
there is no global Docker admission lock. Production backup coherence, direct
native journal exposure, full writer/service integration, authenticated API UAT
and live 16-surface orchestration remain separate gates. Production observations,
deployment pointer, clean canonical checkout and exact-owned cleanup must still
pass before overall success is printed.

## Verification

Run before committing from the new feature worktree:

```sh
git diff --check
python -B -m pytest -q tests/core
python -B scripts/diagnostics/sports-consumption-interruption-drill.py
```

Local unit tests run all 15 real SIGKILL checkpoints with actual Atlas metadata
and explicit non-native PG/Teamarr filesystem fixtures. They also check normal
exit refusal, incomplete import, active cooperative writer refusal, preserved
audit and callback gating. The CT100 diagnostic supplies real strictly prepared
PostgreSQL and native Teamarr state, then verifies final application restarts.
The two numeric ownership cases and native/Docker acceptance require CT100.
