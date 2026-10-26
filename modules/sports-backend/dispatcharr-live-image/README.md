# Dispatcharr verified live source review

This directory contains modified Dispatcharr application source. Upstream:
https://github.com/Dispatcharr/Dispatcharr (AGPL-3.0). The exact base image
is pinned below. Preserve upstream notices and review the license/source
distribution requirements before publishing an image or merging this draft.

This source review pins the running upstream image by digest and verifies the
24 exported base source files before copying 28 changed/new live files. It
excludes the staged VOD and timeshift modifications. The runtime's verified
live mode remains its default `off`; this is not a production rollout.

Inputs: staged archive SHA-256 7cb179a95b06d746327351ce99e57b70a1499cb5d7c64bbea343089b65a123e0; base source SHA-256 0ed5de0113c510ea0dca015afe9d1c6bd0cbebfa8f1c2993db69c2149d13e36e.
Image base: ghcr.io/dispatcharr/dispatcharr@sha256:e764cd3fb3a4b14e0c96eeb830cce645b44ef0a2494838e21462c71dde5abeb4.

CT100 disposable build and tests (no production mounts or runtime mutation):

    ./run-disposable-image-tests.sh

The source suite covers 58 historical live-path tests, nine HEAD and packaging
contracts, and 12 pilot boundary checks (79 total). The disposable image command additionally runs three
private-Redis admission checks; those checks require separate image validation.
Atlas Sports' classifier test is excluded because that source lives in the
separate Atlas policy PR. Django system check requires an ephemeral signing
key and is run separately without a database connection. The shared
live/VOD/timeshift cutover, embedded playback, and production health remain
release gates. Do not set `ATLAS_VERIFIED_LIVE_MODE=strict` or
`ATLAS_RESERVATION_LEDGER_MIGRATED=1` for this review build.

## Current-base reconciliation

This source port starts from PR #220 at 31dd7e14243a2023df7132d46da2fe4e8c11b115.
It retains the current HEAD compatibility contract: network denial occurs before
identity lookup, existing identities receive an empty streaming response without
Content-Length, and no upstream, client, policy claim, or reservation is allocated.
The historical overlay GET body remains AST-identical. The image build runs the
actual Django/DRF HEAD contract in addition to final overlay hash verification.

Run source-only validation without Docker or third-party dependencies:

    python3 -B run-source-tests.py

The core release gate invokes this source suite. Source tests do not prove image
build success, actual Redis admission, live capacity, sharing, or playback.
The original production Dockerfile, Compose selection, mode flags, data, and
running containers are unchanged. Strict activation and ledger migration remain
separate guarded work. Historical staged archive hashes identify provenance;
`overlay_files` binds the reconciled source rather than those historical archives.

Build context regression coverage keeps the manifest and actual framework-test
fixture available to Docker COPY. The guarded image-validation runner stages
only these committed files with readable build-context modes; it does not mount
production data or start the application.

## Live-only pilot source boundary

An opt-in pilot guard now restricts provider playback to managed verified live
Sports. It does not complete VOD/timeshift migration. See
`docs/operations/SPORTS_LIVE_PILOT.md` in the Atlas repository. The guard remains
off unless explicitly configured; this source change grants no activation or
ledger cutover authority. Actual Django/image route validation and guarded
deployment acceptance remain pending. The source suite now includes 12 pilot
checks in addition to the 67 existing checks (79 total).
