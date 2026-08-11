FROM python:3.13-slim

ARG PUID
ARG PGID

RUN test -n "${PUID}" \
    && test -n "${PGID}" \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        coreutils \
    && groupadd --gid "${PGID}" atlas \
    && useradd \
        --uid "${PUID}" \
        --gid atlas \
        --no-create-home \
        --shell /usr/sbin/nologin \
        atlas \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/project-atlas

USER atlas

CMD ["/opt/project-atlas/modules/notifications/scripts/worker.sh"]
