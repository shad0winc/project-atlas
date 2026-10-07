FROM ghcr.io/dispatcharr/dispatcharr@sha256:e764cd3fb3a4b14e0c96eeb830cce645b44ef0a2494838e21462c71dde5abeb4

COPY modules/sports-backend/dispatcharr/apply_patch.py /tmp/atlas-dispatcharr-apply-patch.py
COPY modules/sports-backend/dispatcharr/test_stream_head.py /tmp/atlas-dispatcharr-test-stream-head.py
RUN python /tmp/atlas-dispatcharr-apply-patch.py \
    && python -B /tmp/atlas-dispatcharr-test-stream-head.py \
    && rm -f /tmp/atlas-dispatcharr-apply-patch.py \
        /tmp/atlas-dispatcharr-test-stream-head.py /tmp/atlas-dispatcharr-views.before.py

LABEL project-atlas.component="dispatcharr" \
      project-atlas.patch="head-compatibility-v1"
