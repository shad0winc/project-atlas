# Extracted archive to disposable native runtime

This rehearsal prepares the native baseline from validated archive members rather
than continuing to use only the pre-archive baseline. Production restore and
deployment remain disabled; no existing command or helper source is modified.

## Run before committing

At main baseline `70ad1f3cd60483e36972ad66ded9fb26a3849ccb`:

```bash
git diff --check
python -B -m pytest -q tests/core
python -B scripts/diagnostics/sports-archive-restore-drill.py
```

The entry point reuses the pinned four-writer, backup archive, strict native,
metadata and maintenance fixtures. Within a separately loaded archive support
module, it wraps the existing readback callback in memory. The original readback
and all original source/baseline immutability checks still execute. No disk source
patch or production callback registration is introduced.

## Extraction and native preparation

1. The existing command creates, validates and publishes a private format-3 archive
   while all four disposable counter proxies remain stopped.
2. The actual complete archive and safe-member validators must accept it again.
   Extract only the three fixed backend members to a new private workspace:
   Dispatcharr dump, JWT and detached Teamarr database. Reject existing targets,
   nonregular/duplicate members, members over 512 MiB, bad modes or changed bytes.
   Streaming writes are exclusive, no-follow and fsynced. Archive SHA and extracted
   member SHAs are bound in a private receipt; archive bytes remain unchanged.
3. Create two fresh UUID-derived owned local volumes. Initialize a compatible cold
   PostgreSQL scaffold in the input volume from the preserved fixture cold cluster,
   and copy the *extracted archive dump* there with numeric UID/GID 1000 ownership.
   The output volume starts empty. Both volumes have exact label/driver/reference
   checks; neither is a production path or volume.
4. Invoke the existing pinned nonroot strict PostgreSQL utility with read-only
   input, separate writable output, no network, read-only root and dropped
   capabilities. It restores the extracted dump into its private cloned cluster,
   checks strict schema/global identity contracts and exports a stopped cluster.
   Its dump SHA must equal the extraction receipt. The utility must exit normally;
   remove its exact object and require zero input/output references before copying.
5. Normalize the freshly prepared PostgreSQL cluster into a private candidate.
   JWT and Teamarr files are copied from the extracted archive members. Candidate
   provenance binds archive SHA, dump SHA, utility receipt and all three hashes.
6. After the unchanged archive helper finishes its baseline immutability checks,
   promote these three candidate units into the not-yet-exposed native baseline.
   Preserve prior native units under `PRE_ARCHIVE`, retain the prior capture
   receipt, and bind the new capture to `ARCHIVE_RESTORED.json`. Existing strict
   preparation proof remains historical evidence for the preceding baseline.

Promotion is fixture-only and occurs before the cooperative journal is armed.
Any partial preparation/promotion holds the diagnostic; no crash-resume claim is
made for this new pre-exposure operation. Existing audit files are never overwritten.
All utility objects and volumes are cleaned through their exact owned identifiers.

## Runtime acceptance

The existing native fixture now materializes fresh application volumes from the
archive-derived baseline. The first application startup must observe the dump's
`snapshot` PostgreSQL marker, the expected Teamarr marker and preserved JWT.
After native/metadata consumer writes, detached capture/import and maintenance-
controlled rollback must recover that baseline again. A further restored app
startup and persistence restart must pass, including PostgreSQL absence of the
post-cutover table and the existing numeric UID/GID 1000 metadata reader checks.

The four proxy writers must resume with frozen baseline/counter captures unchanged.
Overall PASS still requires all existing cleanup, production observation,
deployment pointer and clean canonical checkout checks. Fixed progress receipts
contain no raw database/JWT bytes, environment dumps, service logs or raw stderr.

## Limits and test interpretation

The cold PostgreSQL scaffold supplies compatible global roles and configuration
outside the archive dump. This is not a standalone disaster bootstrap from an
archive alone. It proves restoring extracted application data into a separately
prepared compatible cluster and fresh application volumes. Production role/
configuration provisioning, ingress, actual four-service acceptance, complete
16-surface restore and production archive/source coherence remain separate gates.

Metadata archive readback continues to validate real schema, aliases, budget,
cooldown, cache and disabled policy. Runtime metadata is still initialized by the
existing fixture hook; this candidate does not feed extracted metadata into a
production Sports writer or activate refresh. Native apps write owned volumes,
then stopped captures are imported; direct native journal exposure is unchanged.

Local unit tests cover exact three-member extraction, existing extraction refusal,
corrupt archive rejection, size limits, promotion preserving prior units/capture,
bad provenance/hash refusal and existing audit preservation. PostgreSQL bytes in
unit promotion fixtures are explicit unit data. Actual PostgreSQL preparation,
ownership conversion and application starts require CT100 Docker verification.

The private archive and workspace are temporary acceptance evidence. No storage
power-loss, arbitrary Docker admission lock or new 15-case interruption run is
claimed. Packaging scaffolding remains explicitly synthetic where source export
inputs were absent. The Media browse acceptance queue remains after Sports.

Expected intermediate markers:
`ARCHIVE_EXTRACTED_DUMP_PREPARATION=running` and
`ARCHIVE_EXTRACTED_NATIVE_BASELINE_PROMOTED=PASS`.
Overall result: `SYNTHETIC_ARCHIVE_RESTORE_DRILL=PASS` and
`STATE=isolated-extracted-archive-native-restore-not-deployed`.
Follow RC1-first CI/merge, identical main CI/merge and canonical fast-forward only.
