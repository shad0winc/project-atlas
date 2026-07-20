FROM python:3.13-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        coreutils \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/project-atlas

ENV PYTHONPATH="/opt/project-atlas:/opt/project-atlas/modules/sports/src"

CMD ["python3", "/opt/project-atlas/modules/sports/src/worker.py"]
