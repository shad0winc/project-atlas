FROM ghcr.io/dispatcharr/dispatcharr@sha256:e764cd3fb3a4b14e0c96eeb830cce645b44ef0a2494838e21462c71dde5abeb4
COPY verify_base.py /tmp/atlas-verify-base.py
RUN python /tmp/atlas-verify-base.py
COPY overlay/apps/ /app/apps/
COPY install_live_pilot.py /tmp/atlas-install-live-pilot.py
RUN python -B /tmp/atlas-install-live-pilot.py
COPY Dockerfile manifest.json .dockerignore /app/
COPY verify_overlay.py /tmp/atlas-verify-overlay.py
RUN python /tmp/atlas-verify-overlay.py
COPY tests/fixtures/stream_ts_before_head.py /tmp/atlas-dispatcharr-views.before.py
COPY test_stream_head.py /tmp/atlas-dispatcharr-test-stream-head.py
RUN python -B /tmp/atlas-dispatcharr-test-stream-head.py \
    && rm -f /tmp/atlas-dispatcharr-test-stream-head.py /tmp/atlas-dispatcharr-views.before.py
LABEL project-atlas.patch="verified-live-head-compatibility-v1"
