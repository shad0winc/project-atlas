FROM ghcr.io/dispatcharr/dispatcharr@sha256:e764cd3fb3a4b14e0c96eeb830cce645b44ef0a2494838e21462c71dde5abeb4
COPY verify_base.py /tmp/atlas-verify-base.py
RUN python /tmp/atlas-verify-base.py
COPY overlay/apps/ /app/apps/
COPY verify_overlay.py /tmp/atlas-verify-overlay.py
RUN python /tmp/atlas-verify-overlay.py
