FROM ghcr.io/pharaoh-labs/teamarr@sha256:d846ec078cde27f68e94f5fc3eec7f1ec29eca11f653b157ac352fef84b73c0c

COPY modules/sports-backend/teamarr/apply_patch.py \
    /tmp/atlas-teamarr-apply-patch.py

RUN python3 /tmp/atlas-teamarr-apply-patch.py \
    && rm -f /tmp/atlas-teamarr-apply-patch.py

LABEL project-atlas.component="teamarr" \
      project-atlas.patch="trusted-date-safety-v3"
