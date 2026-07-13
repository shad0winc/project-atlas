FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        coreutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/project-atlas

CMD ["python3", "/opt/project-atlas/modules/sports/src/worker.py"]
