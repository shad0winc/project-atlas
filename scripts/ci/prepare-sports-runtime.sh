#!/usr/bin/env bash
# CI only. The workflow gives setup its own bounded time budget.
set -euo pipefail

if command -v ffmpeg >/dev/null 2>&1 &&
   command -v ffprobe >/dev/null 2>&1 &&
   ffmpeg -version >/dev/null 2>&1 &&
   ffprobe -version >/dev/null 2>&1; then
  echo 'Sports CI: using available FFmpeg tools'
else
  echo 'Sports CI: installing FFmpeg tools'
  sudo env DEBIAN_FRONTEND=noninteractive apt-get update
  sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ffmpeg
  hash -r
fi

# Missing or broken tools must fail setup; integration tests remain mandatory.
ffmpeg -version
ffprobe -version
