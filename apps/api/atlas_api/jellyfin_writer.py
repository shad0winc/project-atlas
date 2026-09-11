"""Private Jellyfin operational mutation boundary."""

from __future__ import annotations

import argparse
import hmac
import os
import threading
import time
from collections.abc import Callable

import uvicorn
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    status,
)

from atlas.media.jellyfin_admin import (
    JellyfinAdminClient,
    JellyfinAdminError,
)


REFRESH_TASK_KEY = "RefreshGuide"
REFRESH_TIMEOUT_SECONDS = 60.0
REFRESH_POLL_SECONDS = 0.5


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value or value == "CHANGE_ME":
        raise RuntimeError(f"{name} is required.")

    return value


def _positive_float_environment(
    name: str,
    default: str,
) -> float:
    raw = os.getenv(name, default).strip()

    try:
        value = float(raw)
    except ValueError as error:
        raise RuntimeError(
            f"{name} must be numeric."
        ) from error

    if value <= 0:
        raise RuntimeError(
            f"{name} must be greater than zero."
        )

    return value


SERVICE_TOKEN = _required_environment(
    "ATLAS_JELLYFIN_WRITER_TOKEN"
)
JELLYFIN_URL = _required_environment(
    "ATLAS_JELLYFIN_URL"
)
JELLYFIN_API_KEY = _required_environment(
    "ATLAS_JELLYFIN_API_KEY"
)
JELLYFIN_TIMEOUT_SECONDS = _positive_float_environment(
    "ATLAS_JELLYFIN_TIMEOUT_SECONDS",
    "10",
)

_REFRESH_LOCK = threading.Lock()


class JellyfinLiveTvRefreshBusyError(RuntimeError):
    """A Live TV refresh is already active or Jellyfin is busy."""


class JellyfinLiveTvRefreshTimeoutError(RuntimeError):
    """The bounded Jellyfin Live TV refresh did not return to idle."""


class JellyfinLiveTvRefreshStateError(RuntimeError):
    """Jellyfin returned an unexpected scheduled-task state."""


def _require_service_token(
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
) -> None:
    prefix = "Bearer "

    if (
        authorization is None
        or not authorization.startswith(prefix)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid service authentication is required.",
        )

    supplied = authorization[len(prefix):]

    if not hmac.compare_digest(
        supplied,
        SERVICE_TOKEN,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid service authentication is required.",
        )


def _jellyfin_admin_client() -> JellyfinAdminClient:
    return JellyfinAdminClient(
        JELLYFIN_URL,
        JELLYFIN_API_KEY,
        timeout_seconds=JELLYFIN_TIMEOUT_SECONDS,
    )


def _refresh_live_tv(
    client: JellyfinAdminClient,
    *,
    timeout_seconds: float = REFRESH_TIMEOUT_SECONDS,
    poll_seconds: float = REFRESH_POLL_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    if timeout_seconds <= 0:
        raise ValueError(
            "Refresh timeout must be greater than zero."
        )

    if poll_seconds <= 0:
        raise ValueError(
            "Refresh poll interval must be greater than zero."
        )

    task = client.find_scheduled_task_by_key(
        REFRESH_TASK_KEY
    )

    if task.state != "Idle":
        raise JellyfinLiveTvRefreshBusyError(
            "Jellyfin Live TV refresh is not idle."
        )

    client.start_scheduled_task(task.task_id)

    deadline = monotonic() + timeout_seconds

    while True:
        current = client.get_scheduled_task(
            task.task_id
        )

        if current.key != REFRESH_TASK_KEY:
            raise JellyfinLiveTvRefreshStateError(
                "Jellyfin Live TV refresh identity changed."
            )

        if current.state == "Idle":
            return

        if current.state != "Running":
            raise JellyfinLiveTvRefreshStateError(
                "Jellyfin Live TV refresh returned an "
                "unexpected state."
            )

        now = monotonic()

        if now >= deadline:
            raise JellyfinLiveTvRefreshTimeoutError(
                "Jellyfin Live TV refresh timed out."
            )

        sleep(
            min(
                poll_seconds,
                max(0.0, deadline - now),
            )
        )


app = FastAPI(
    title="Atlas Jellyfin Writer",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/internal/v1/jellyfin/live-tv/refresh",
    dependencies=[Depends(_require_service_token)],
)
def refresh_live_tv() -> dict[str, str]:
    if not _REFRESH_LOCK.acquire(blocking=False):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Jellyfin Live TV refresh is already active.",
        )

    try:
        try:
            _refresh_live_tv(
                _jellyfin_admin_client()
            )
        except JellyfinLiveTvRefreshBusyError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Jellyfin Live TV refresh is not idle.",
            ) from error
        except JellyfinLiveTvRefreshTimeoutError as error:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Jellyfin Live TV refresh timed out.",
            ) from error
        except (
            JellyfinLiveTvRefreshStateError,
            JellyfinAdminError,
        ) as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Jellyfin Live TV refresh failed.",
            ) from error
    finally:
        _REFRESH_LOCK.release()

    return {
        "status": "completed",
        "task_key": REFRESH_TASK_KEY,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        default="127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8004,
    )
    args = parser.parse_args()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
