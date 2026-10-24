# Dispatcharr verified live source review

This directory contains modified Dispatcharr application source. Upstream:
https://github.com/Dispatcharr/Dispatcharr (AGPL-3.0). The exact base image
is pinned below. Preserve upstream notices and review the license/source
distribution requirements before publishing an image or merging this draft.

This source review pins the running upstream image by digest and verifies the
18 exported base source files before copying 27 changed/new live files. It
excludes the staged VOD and timeshift modifications. The runtime's verified
live mode remains its default `off`; this is not a production rollout.

Inputs: staged archive SHA-256 7cb179a95b06d746327351ce99e57b70a1499cb5d7c64bbea343089b65a123e0; base source SHA-256 0ed5de0113c510ea0dca015afe9d1c6bd0cbebfa8f1c2993db69c2149d13e36e.
Image base: ghcr.io/dispatcharr/dispatcharr@sha256:e764cd3fb3a4b14e0c96eeb830cce645b44ef0a2494838e21462c71dde5abeb4.

CT100 disposable build and tests (no production mounts or runtime mutation):

    ./run-disposable-image-tests.sh

The suite covers 58 live-path tests and three private-Redis admission checks.
Atlas Sports' classifier test is excluded because that source lives in the
separate Atlas policy PR. Django system check requires an ephemeral signing
key and is run separately without a database connection. The shared
live/VOD/timeshift cutover, embedded playback, and production health remain
release gates. Do not set `ATLAS_VERIFIED_LIVE_MODE=strict` or
`ATLAS_RESERVATION_LEDGER_MIGRATED=1` for this review build.
