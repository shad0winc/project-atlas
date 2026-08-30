#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hmac
import json
import os
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from providers.registry import enabled_providers
from subscriptions import create_subscription, load_subscriptions

MAX_BODY_BYTES = 16 * 1024


def _provider(name: str):
    normalized = name.strip().lower()
    providers = {
        provider.name: provider
        for provider in enabled_providers()
    }
    provider = providers.get(normalized)
    if provider is None:
        raise LookupError(
            f"Sports provider is unavailable: {normalized}"
        )
    return provider


class Handler(BaseHTTPRequestHandler):
    server_version = "AtlasSportsPrivate/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _authorized(self) -> bool:
        expected = os.getenv(
            "ATLAS_SPORTS_WRITER_TOKEN",
            "",
        ).strip()
        supplied = self.headers.get(
            "Authorization",
            "",
        )
        if not expected or not supplied.startswith("Bearer "):
            return False
        return hmac.compare_digest(
            supplied[7:].strip(),
            expected,
        )

    def _json(
        self,
        status: HTTPStatus,
        payload: dict[str, Any],
    ) -> None:
        encoded = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _require_auth(self) -> bool:
        if self._authorized():
            return True
        self._json(
            HTTPStatus.UNAUTHORIZED,
            {"error": "Unauthorized."},
        )
        return False

    def _backend_unavailable(self) -> None:
        self._json(
            HTTPStatus.SERVICE_UNAVAILABLE,
            {
                "code": "sports_backend_unavailable",
                "error": "Sports provider or state service is unavailable.",
            },
        )

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/health":
            self._json(
                HTTPStatus.OK,
                {"status": "ok"},
            )
            return
        if parsed.path != "/internal/v1/events":
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": "Not found."},
            )
            return
        if not self._require_auth():
            return

        params = urllib.parse.parse_qs(
            parsed.query,
            keep_blank_values=False,
        )
        user_id = str(
            params.get("user_id", [""])[0]
        ).strip()
        provider_name = str(
            params.get("provider", [""])[0]
        ).strip()
        event_ids = [
            str(value).strip()
            for value in params.get("event_id", [])
            if str(value).strip()
        ]
        if not user_id or not provider_name:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "user_id and provider are required."},
            )
            return

        try:
            provider = _provider(provider_name)
        except LookupError as exc:
            self._json(
                HTTPStatus.NOT_FOUND,
                {
                    "code": "provider_not_found",
                    "error": str(exc),
                },
            )
            return
        except Exception:
            self._backend_unavailable()
            return

        try:
            subscriptions = load_subscriptions()
            requested_ids = {
                str(subscription.get("id", "")).strip()
                for subscription in subscriptions
                if (
                    isinstance(subscription, dict)
                    and str(
                        subscription.get("type", "")
                    ).strip().lower() == "event"
                    and str(
                        subscription.get("provider", "")
                    ).strip().lower() == provider.name
                    and str(
                        subscription.get("user", "")
                    ).strip() == user_id
                    and bool(subscription.get("enabled", True))
                )
            }

            if event_ids:
                provider_events: list[dict[str, Any]] = []
                for event_id in event_ids:
                    raw_event = provider.fetch_event(event_id)
                    if raw_event is None:
                        continue
                    provider_events.append(
                        dict(provider.normalize_event(raw_event))
                    )
            else:
                provider_events = [
                    dict(event)
                    for event in provider.fetch_games()
                ]

        except Exception:
            self._backend_unavailable()
            return

        events: list[dict[str, Any]] = []
        for event in provider_events:
            provider_event_id = str(
                event.get("provider_event_id", "")
            ).strip()
            if not provider_event_id:
                continue
            event["requested"] = (
                provider_event_id in requested_ids
            )
            events.append(event)

        self._json(
            HTTPStatus.OK,
            {"events": events},
        )

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path != "/internal/v1/events/request":
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": "Not found."},
            )
            return
        if not self._require_auth():
            return

        try:
            length = int(
                self.headers.get("Content-Length", "0")
            )
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"error": "Request body is too large."},
            )
            return

        try:
            payload = json.loads(
                self.rfile.read(length).decode("utf-8")
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Invalid JSON."},
            )
            return
        if not isinstance(payload, dict):
            self._json(
                HTTPStatus.BAD_REQUEST,
                {"error": "JSON object required."},
            )
            return

        user_id = str(payload.get("user_id", "")).strip()
        provider_name = str(
            payload.get("provider", "")
        ).strip()
        event_id = str(
            payload.get("provider_event_id", "")
        ).strip()

        if not user_id or not provider_name or not event_id:
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": (
                        "user_id, provider, and "
                        "provider_event_id are required."
                    )
                },
            )
            return

        try:
            provider = _provider(provider_name)
        except LookupError as exc:
            self._json(
                HTTPStatus.NOT_FOUND,
                {
                    "code": "provider_not_found",
                    "error": str(exc),
                },
            )
            return
        except Exception:
            self._backend_unavailable()
            return

        try:
            raw_event = provider.fetch_event(event_id)
        except Exception:
            self._backend_unavailable()
            return

        if raw_event is None:
            self._json(
                HTTPStatus.NOT_FOUND,
                {
                    "code": "event_not_found",
                    "error": "Sports event was not found.",
                },
            )
            return

        try:
            normalized = provider.normalize_event(raw_event)
        except Exception:
            self._backend_unavailable()
            return

        name = str(
            normalized.get("name", "")
        ).strip()
        if not name:
            self._json(
                HTTPStatus.BAD_GATEWAY,
                {
                    "error": (
                        "Sports provider returned an "
                        "event without a name."
                    )
                },
            )
            return

        try:
            subscription, created = create_subscription(
                "event",
                provider.name,
                event_id,
                name,
                user_id,
            )
        except Exception:
            self._backend_unavailable()
            return

        self._json(
            HTTPStatus.OK,
            {
                "subscription": subscription,
                "created": created,
            },
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8003)
    args = parser.parse_args()

    if not os.getenv(
        "ATLAS_SPORTS_WRITER_TOKEN",
        "",
    ).strip():
        raise SystemExit(
            "ATLAS_SPORTS_WRITER_TOKEN is required"
        )

    server = ThreadingHTTPServer(
        (args.host, args.port),
        Handler,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
