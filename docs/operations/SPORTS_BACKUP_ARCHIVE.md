# Complete private backup archive rehearsal

This adds archive creation, validation, publication and bounded artifact readback
inside the previously verified four-writer native capture fence. It does not
enable live restore, production backup publication or deployment.

## Run and scope

Before committing, at main baseline `da798030f5c23949f9a65b6ccd798a9df6ad80d1`:

```bash
git diff --check
python -B -m pytest -q tests/core
python -B scripts/diagnostics/sports-backup-archive-drill.py
```

The entry point reuses the existing strict native/metadata/maintenance fixture
and four counter-writer proxies. It changes no existing command or helper.
Its strict-preparation callback runs the existing dump preparation, then performs
archive acceptance before the four stopped proxies may restart.

The actual `atlas_command_backup` function is sourced from the pinned repository
source. It operates on a private project copy and private runtime/config paths.
The project copy includes available selected source roots and its own synthetic
git baseline. Non-exported environment example, version, changelog or configuration
inputs have explicitly synthetic private fallbacks; a missing root Sports compose
uses the checked module compose source. A fixture note is included in archived
docs. This does not certify production source-package completeness. No backup
temporary manifest is written into the canonical checkout or candidate worktree.

The actual registry, snapshot copying, checksum generation, metadata capture,
tar creation, partial-archive validation, final publication and retention code
run unchanged. The native capture boundary alone is a fixture adapter installed
after the command reloads its recovery library. It supplies three already
captured artifacts and invokes the actual backend staged validator. This avoids
the existing backend capture routine's fixed production container names.

## Archive contents and evidence

- All sixteen actual registry rows are represented. Fourteen required surfaces
  contain explicitly synthetic records; the two optional surfaces remain absent
  and must be declared `absent-optional`. These records do not attest real users
  or cross-service business transactions.
- PostgreSQL dump bytes are copied from the owned stopped fixture volume. Their
  SHA must equal the strict preparation receipt's dump SHA. This binds the archive
  to the dump used to prepare the subsequently accepted native baseline.
- JWT and detached Teamarr SQLite bytes are copied from that preserved baseline.
  Backend manifest/checksums and real staged/archive validators must accept them.
- Actual Atlas metadata schema, aliases, cached fixture payload, attempt budget,
  cooldown and disabled policy are captured by the normal metadata backup helper.
  The source uses the existing fixed `new` fixture generation, independent of
  production data. Policy ownership/modes match its independent reader contract.
- The actual command must publish exactly one regular private mode-0600 format-3
  archive. Both the complete archive validator and safe-member validator must
  pass. No `.partial`, temporary snapshot or project manifest may remain.
- Selected native members are read back without extraction and must match payload
  SHA values. Metadata database/policy members are written only to a fresh private
  reader fixture and checked with the actual Atlas metadata acceptance helper.
  The archive SHA must remain unchanged by readback.

Configuration/runtime and prepared native payload source bytes must be unchanged
by backup creation. The original stopped dump and complete strict native baseline
must remain unchanged, and detached native ownership must still hold afterwards.
The archive fixture is then removed before the counter proxies resume. The normal
four-writer unchanged-baseline check and complete native/metadata consumption,
rollback, restored app/persistence starts and maintenance release follow.

## Failure acceptance

Local unit tests run the real command and archive validators with explicit unit
native payloads (a PGDMP header is not a real PostgreSQL dump). Tests cover complete
format-3 publication/readback, missing required state, bad native checksums,
symlink refusal, modified archived native bytes, and refusal at the final archive
validation gate after actual tar creation. Failed publication must leave neither
a final archive nor a partial artifact in the private backup directory.

CT100 supplies the real dump, SQLite and JWT fixtures, strict preparation and
native application acceptance. The full core suite and Docker entry point remain
required before RC1/main integration. Only fixed progress and typed receipts are
printed; raw stdout/stderr, archive payloads, identities and credentials are not.

## Limits

This exercises the existing command against private inputs, not production
ingress, the four actual service implementations, live-state coherence or storage
durability under power loss. Private publication is temporary acceptance evidence;
it is not retained as an operator recovery backup. No real backup retention target
is touched. No incomplete archive extraction or 16-surface live restore is enabled.

Native application acceptance later uses the existing prepared baseline whose dump
and identity/SQLite bytes are bound to the archive. It does not reconstruct and
boot a new native cluster directly from extracted archive members. That full
archive-to-restored-runtime path remains a separate integration gate.

The helper bounds each native/readback member to 512 MiB and the compressed archive
to 1 GiB. Configuration source copying uses existing per-tree bounds. The operation
assumes a trusted serial controller; it introduces no arbitrary Docker admission
lock or new crash-resumable archive journal. No earlier SIGKILL case is rerun here.

Expect `BACKUP_ARCHIVE_FORMAT3_VALIDATED_PUBLISHED_AND_ROUNDTRIP=PASS`, followed by
the existing fixture acceptance and `SYNTHETIC_BACKUP_ARCHIVE_DRILL=PASS`.
Final state: `STATE=isolated-complete-backup-archive-not-deployed`.
Follow RC1-first CI/merge, identical main CI/merge and canonical fast-forward only.
The agreed Media browse improvements remain queued after Sports.
