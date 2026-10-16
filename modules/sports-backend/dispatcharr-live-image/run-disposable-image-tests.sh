#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
image=atlas-dispatcharr-live-review:20260928
docker build --pull=false --network=none -t "$image" "$root"
docker run --rm -i --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m,mode=1777 \
  --security-opt no-new-privileges --cap-drop ALL \
  --pids-limit 128 --memory 256m --cpus 1 --user 65534:65534 \
  -e ATLAS_VERIFIED_LIVE_MODE=off \
  -v "$root/tests:/app/tests:ro" --entrypoint python "$image" \
  -m unittest discover -s /app/tests -p 'test_*.py' -q
docker run --rm -i --network none --read-only \
  --tmpfs /tmp:rw,nosuid,nodev,size=64m,mode=1777 \
  --security-opt no-new-privileges --cap-drop ALL \
  --pids-limit 128 --memory 256m --cpus 1 --user 65534:65534 \
  -e ATLAS_VERIFIED_LIVE_MODE=off \
  -v "$root/tests:/app/tests:ro" --entrypoint python "$image" \
  /app/tests/real_redis_viewer_policy.py
echo disposable_image_tests=PASS
