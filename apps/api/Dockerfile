FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/srv:/srv/apps/api

WORKDIR /srv/apps/api

RUN groupadd --system atlas \
    && useradd \
        --system \
        --gid atlas \
        --home-dir /srv \
        --shell /usr/sbin/nologin \
        atlas

COPY apps/api/pyproject.toml /srv/apps/api/pyproject.toml
COPY apps/api/atlas_api /srv/apps/api/atlas_api
COPY atlas /srv/atlas

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir .

USER atlas

EXPOSE 8000

HEALTHCHECK \
    --interval=30s \
    --timeout=5s \
    --start-period=10s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

CMD ["uvicorn", "atlas_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
