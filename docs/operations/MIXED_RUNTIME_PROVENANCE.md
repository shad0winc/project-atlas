# Mixed Sports runtime provenance

This contract describes a deployment whose native component recipe archives
remain distinct from a repaired Sports writer's copied code. It does not
activate services or provide permission to publish a baseline.

## Current accepted preparation

At 2026-10-19T01:24:16Z, candidate
`baseline-reconciliation-20261019T012409Z-e98c967e0b` was prepared under
`deployments/repairs/reconciliation-prepared-bhdbe6on/candidate`. Its 21-file
manifest SHA256 is
`ebf18fbaabf7bd120baed0710cb5d2c22a8cb0e0f554c352db38ab04d17f2d2c`.
Native image and historical Notifications verification passed; status remains
`prepared`. The original lock, maintenance, current pointer, failed transaction,
backups and four linked repair journals remain preserved.

Core, the scheduler publication archive and the base Ingress recipe remain
`f8696d95bbf4488d95c2243e54c305010ae5b22c`. The Sports controller source and
the explicitly overridden Ingress Sports writer source are
`d90c3ead0bf01e851fdd8033656e68934ea14977`. Notifications remains historical
`79cf73747f9a979ea02fb77446f2fa61df8e3451` at `/opt/project-atlas`.
Component commits describe base recipes; `service-sources.json` explicitly
describes the writer exception. They do not claim every Ingress image was built
from the repaired source.

## Schema and enforcement

`requires_mixed_runtime_contract=1`, `runtime_provenance_schema=1` and the
Ingress source-mode marker require the service ledger, tracked repair manifest,
recovery chain, repair source archive, activation and historical acceptance
evidence. Removing a ledger while leaving its manifest or other supplements
does not turn the record into a legacy baseline.

The complete flat-file checksum manifest is checked before interpreting the
ledger. Known native `recovery-core.*`, `recovery-ingress.*` and
`recovery-sports.*` directories remain separate recovery journals. Unknown
directories and symlink evidence are refused. Git archive commit markers,
tracked blob identities and executable modes bind the repair archive. The
writer COPY map is derived from the archived Dockerfile, then checked against
the ledger. Core and Ingress archive commit markers retain their recipe
identities. Historical current/lock fingerprints are historical observations;
they are not live pins after successful publication.

Native runtime verification additionally checks the running writer's image and
copied files, the running controller's image and single read-only source bind,
all tracked controller blobs/executable bits and the exact five-file private
configuration overlay. Extra controller Python files are refused. A Sports
exclusion continues to check the Ingress writer while excluding the controller.
The same live contract runs before authoritative scheduler-source publication.

## Update and recovery behavior

Core-only and Ingress-only updates from a mixed baseline refuse before durable
lock acquisition in the normal update entry point, and before record creation
or image aliasing in the lower-level preparation primitive. Such updates need
a separately reviewed provenance transformation. Component adoption also
refuses to discard the ledger. A future all-scope update remains possible
through the normal guards; no update is authorized during this held recovery.

Native restoration validates the mixed baseline before extracting its source.
For Sports it restores the exact private configuration overlay from the retained
original generation into the native records/<transaction>/recovery-sports.*
directory before Compose activation. All five source files are validated
before any destination configuration is written. Missing or changed retained
configuration fails closed. Preserve the private repair generation permanently
with its linked journals; the archive deliberately contains no private .env.

Rollback reconciliation inherits the ledger, tracked manifest, writer source
archive and recovery history from the same baseline as its component archives.
Failed-after-apply reconciliation similarly inherits them from its applied
transaction when applicable. Copies retain the original failed update identity
and separately record the immediate reconciliation transaction. Native status
changes and new reconciliations reseal the complete evidence manifest. Failures
continue to retain maintenance and durable recovery ownership.

## Validation and boundaries

CT100 validation of the uncommitted native integration passed on 2026-10-19 UTC:

| Surface | Observed result |
|---|---|
| Focused installation | 129 passed; 2 subtests passed |
| Targeted corrections | 94 passed; 194 subtests passed |
| Affected deployment modules | 148 passed; 2 subtests passed |
| Full Core | 5610 passed; 12 skipped; 1758 subtests passed |
| API | 884 passed; 14 warnings; 27 subtests passed |
| Sports integration | All 5 programs passed |
| Portal | Lint, type-check, 118 test files / 661 tests, production build passed |
| Release Contracts | 35 shell files parsed; deployment safety checks passed |

Core compiled 624 Python files without bytecode; remaining surfaces compiled
another 243. These are CT100 observations, not protected RC/main CI results.
The full Core receipt is
`/var/tmp/atlas-mixed-runtime-core-isolated-uurrxzjr/receipt.json` (SHA256
`e5e96038a8a5a5de74f7f9498dfe35a9f8d4304994984d87c7ebfc81111bfa6a`).
Remaining-check evidence is
`/var/tmp/atlas-mixed-runtime-remaining-named-fggqqg9u/receipt.json`.

The initial full run, a later run with a conflicting deployment-directory
override, and the npm preflight failure remain preserved as failed attempts.
Core used an owned disposable checkout as UID/GID1000 with cleared groups.
The remaining suites used the existing nobody UID/GID65534 because UID1000
has no NSS account entry for Node home discovery. npm configuration, cache,
state and generated output stayed private. An import guard verified candidate
API/Core/Sports origins and refused historical application imports; the Sports
suite's legacy absolute-path fallback did not select historical code.

Three targeted corrections retained partial-update refusal while avoiding a
redundant all-scope guard call, pinned the offline provider fixture's discovery
date independently of host date, and kept the canonical media-request root
selection test from inspecting a real host registry. Provider runtime behavior
was not changed by those corrections. Maintenance, original lock ownership,
current baseline, failed transaction, linked journals and the prepared candidate
remained preserved. The complete Core suite was not repeated for the remaining
surfaces. The 12 Core skips and 14 API warnings remain reported; this record
does not classify them as release waivers.

This patch provides provenance enforcement and inheritance only. Publication
still needs an independently reviewed finalizer, clean pinned canonical source,
fresh private provider/runtime/Doctor/Verify, controlled public acceptance and
process-death/failure handling while preserving original lock owner bytes.
The prepared candidate remains immutable and unpublished. Record verification
does not establish backup operational restore or production power-loss proof.
RC1 promotion and CI must precede the identical main promotion; merge is
separate from any host checkout advancement or production deployment action.
