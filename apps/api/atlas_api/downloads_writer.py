from __future__ import annotations

import argparse
import hmac
import json
import os
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from atlas.downloads.job_ids import is_opaque_job_id, opaque_job_id


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or value == "CHANGE_ME":
        raise RuntimeError(f"{name} is required.")
    return value


SERVICE_TOKEN = _required_environment("ATLAS_DOWNLOADS_WRITER_TOKEN")
JOB_ID_KEY = _required_environment("ATLAS_DOWNLOADS_JOB_ID_KEY")
QBITTORRENT_BASE_URL = os.getenv(
    "ATLAS_QBITTORRENT_BASE_URL",
    "http://127.0.0.1:8080",
).strip().rstrip("/")
QBITTORRENT_USERNAME = _required_environment("ATLAS_QBITTORRENT_USERNAME")
QBITTORRENT_PASSWORD = _required_environment("ATLAS_QBITTORRENT_PASSWORD")
TIMEOUT_SECONDS = 5.0


def _require_service_token(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    prefix = "Bearer "
    if authorization is None or not authorization.startswith(prefix):
        raise HTTPException(status_code=401, detail="Valid service authentication is required.")
    supplied = authorization[len(prefix):]
    if not hmac.compare_digest(supplied, SERVICE_TOKEN):
        raise HTTPException(status_code=401, detail="Valid service authentication is required.")


class DownloadActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_id: str
    action: str


def _authenticated_opener():
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    request = Request(
        f"{QBITTORRENT_BASE_URL}/api/v2/auth/login",
        data=urlencode({
            "username": QBITTORRENT_USERNAME,
            "password": QBITTORRENT_PASSWORD,
        }).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": QBITTORRENT_BASE_URL,
        },
        method="POST",
    )
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            code = getattr(response, "status", None)
            payload = response.read(64).decode("utf-8", errors="replace").strip()
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise HTTPException(status_code=502, detail="qBittorrent authentication failed.") from error

    if (code == 204 and payload == "") or (code == 200 and payload == "Ok."):
        return opener
    raise HTTPException(status_code=502, detail="qBittorrent authentication failed.")


def _resolve_torrent_hash(opener: Any, job_id: str) -> str:
    if not is_opaque_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid download job identifier.")

    request = Request(
        f"{QBITTORRENT_BASE_URL}/api/v2/torrents/info",
        headers={"Accept": "application/json", "Referer": QBITTORRENT_BASE_URL},
        method="GET",
    )
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise HTTPException(status_code=502, detail="qBittorrent job lookup failed.") from error

    try:
        rows = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=502, detail="qBittorrent returned invalid job data.") from error
    if not isinstance(rows, list):
        raise HTTPException(status_code=502, detail="qBittorrent returned invalid job data.")

    matches: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        torrent_hash = str(row.get("hash") or "").strip()
        if torrent_hash and opaque_job_id(torrent_hash, JOB_ID_KEY) == job_id:
            matches.append(torrent_hash)

    if len(matches) != 1:
        raise HTTPException(status_code=404, detail="Download job not found.")
    return matches[0]


def _post_mutation(opener: Any, endpoint: str, payload: dict[str, str]) -> None:
    request = Request(
        f"{QBITTORRENT_BASE_URL}{endpoint}",
        data=urlencode(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": QBITTORRENT_BASE_URL,
        },
        method="POST",
    )
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            response.read(64)
    except (HTTPError, URLError, TimeoutError, OSError) as error:
        raise HTTPException(status_code=502, detail="qBittorrent mutation failed.") from error


app = FastAPI(
    title="Atlas Downloads Writer",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/internal/v1/downloads/action",
    dependencies=[Depends(_require_service_token)],
)
def mutate_download(request: DownloadActionRequest) -> dict[str, str]:
    action = request.action.strip()
    job_id = request.job_id.strip()

    actions: dict[str, tuple[str, dict[str, str]]] = {
        "stop_seeding": ("/api/v2/torrents/stop", {}),
        "resume": ("/api/v2/torrents/start", {}),
        "remove_job": ("/api/v2/torrents/delete", {"deleteFiles": "false"}),
    }
    if action not in actions:
        raise HTTPException(status_code=400, detail="Unsupported download action.")

    opener = _authenticated_opener()
    torrent_hash = _resolve_torrent_hash(opener, job_id)
    endpoint, extra = actions[action]
    _post_mutation(opener, endpoint, {"hashes": torrent_hash, **extra})

    return {"status": "accepted", "action": action, "job_id": job_id}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
