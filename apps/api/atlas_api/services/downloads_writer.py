from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DownloadsWriterError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


class DownloadsWriterClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.base_url = base_url.strip().rstrip("/")
        self.token = token.strip()
        self.timeout_seconds = timeout_seconds
        if not self.base_url:
            raise ValueError("Downloads writer URL is required.")
        if not self.token or self.token == "CHANGE_ME":
            raise ValueError("Downloads writer token is required.")
        if timeout_seconds <= 0:
            raise ValueError("Downloads writer timeout must be positive.")

    def mutate(self, job_id: str, action: str) -> dict[str, Any]:
        request = Request(
            f"{self.base_url}/internal/v1/downloads/action",
            data=json.dumps({"job_id": job_id, "action": action}).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as error:
            try:
                body = json.loads(error.read().decode("utf-8"))
                message = str(body.get("detail") or "Downloads writer rejected the request.")
            except (ValueError, UnicodeDecodeError):
                message = "Downloads writer rejected the request."
            raise DownloadsWriterError(message, status_code=error.code) from error
        except (URLError, TimeoutError, OSError) as error:
            raise DownloadsWriterError("Downloads writer is unavailable.", status_code=502) from error

        try:
            result = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            raise DownloadsWriterError("Downloads writer returned an invalid response.") from error
        if not isinstance(result, dict):
            raise DownloadsWriterError("Downloads writer returned an invalid response.")
        return result
