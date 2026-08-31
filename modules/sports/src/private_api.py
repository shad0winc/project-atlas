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
from subscriptions import (
    create_subscription,
    load_subscriptions,
    normalize_subscription,
    remove_subscription,
)

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

    def _provider_rate_limited(self, error: Exception) -> None:
        retry_after = max(
            1,
            min(
                int(getattr(error, "retry_after_seconds", 60)),
                300,
            ),
        )
        self.send_response(HTTPStatus.TOO_MANY_REQUESTS)
        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8",
        )
        self.send_header("Retry-After", str(retry_after))
        payload = json.dumps(
            {
                "code": "sports_provider_rate_limited",
                "error": "Sports provider is temporarily rate limited.",
                "retry_after_seconds": retry_after,
            },
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    @staticmethod
    def _safe_team(team: dict[str, Any]) -> dict[str, str]:
        return {
            "id": str(team.get("id", team.get("idTeam", ""))).strip(),
            "name": str(team.get("name", team.get("strTeam", ""))).strip(),
            "sport": str(team.get("sport", team.get("strSport", ""))).strip(),
            "league": str(team.get("league", team.get("strLeague", ""))).strip(),
        }

    @staticmethod
    def _safe_league(league: dict[str, Any]) -> dict[str, str]:
        return {
            "id": str(league.get("id", league.get("idLeague", ""))).strip(),
            "name": str(league.get("name", league.get("strLeague", ""))).strip(),
            "sport": str(league.get("sport", league.get("strSport", ""))).strip(),
        }

    @staticmethod
    def _user_subscriptions(user_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw in load_subscriptions():
            if not isinstance(raw, dict):
                continue
            try:
                subscription = normalize_subscription(raw)
            except ValueError:
                continue
            if str(subscription.get("user", "")).strip() == user_id:
                result.append(subscription)
        return result

    def _read_payload(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "Request body is too large."})
            return None
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON."})
            return None
        if not isinstance(payload, dict):
            self._json(HTTPStatus.BAD_REQUEST, {"error": "JSON object required."})
            return None
        return payload

    def do_GET(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/health":
            self._json(HTTPStatus.OK, {"status": "ok"})
            return
        if not self._require_auth():
            return

        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
        user_id = str(params.get("user_id", [""])[0]).strip()
        provider_name = str(params.get("provider", ["thesportsdb"])[0]).strip()

        if parsed.path == "/internal/v1/subscriptions":
            if not user_id:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "user_id is required."})
                return
            try:
                subscriptions = self._user_subscriptions(user_id)
            except Exception:
                self._backend_unavailable()
                return
            self._json(HTTPStatus.OK, {"subscriptions": subscriptions})
            return

        if parsed.path in {"/internal/v1/search/teams", "/internal/v1/search/leagues"}:
            query = str(params.get("query", [""])[0]).strip()
            if not query or not provider_name:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "query and provider are required."})
                return
            try:
                provider = _provider(provider_name)
                if parsed.path.endswith("/teams"):
                    raw = provider.search_teams(query)
                    results = [self._safe_team(dict(item)) for item in raw if isinstance(item, dict)]
                    results = [item for item in results if item["id"] and item["name"]]
                    self._json(HTTPStatus.OK, {"teams": results})
                else:
                    raw = provider.search_leagues(query)
                    results = [self._safe_league(dict(item)) for item in raw if isinstance(item, dict)]
                    results = [item for item in results if item["id"] and item["name"]]
                    self._json(HTTPStatus.OK, {"leagues": results})
            except LookupError:
                self._json(HTTPStatus.NOT_FOUND, {"code": "provider_not_found", "error": "Sports provider is unavailable."})
            except Exception as exc:
                if getattr(exc, "provider_rate_limited", False):
                    self._provider_rate_limited(exc)
                else:
                    self._backend_unavailable()
            return

        if parsed.path != "/internal/v1/events":
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        event_ids = [str(value).strip() for value in params.get("event_id", []) if str(value).strip()]
        team_ids = [str(value).strip() for value in params.get("team_id", []) if str(value).strip()]
        league_ids = [str(value).strip() for value in params.get("league_id", []) if str(value).strip()]
        if not user_id or not provider_name:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "user_id and provider are required."})
            return
        try:
            provider = _provider(provider_name)
            requested_ids = {
                str(subscription.get("id", "")).strip()
                for subscription in self._user_subscriptions(user_id)
                if str(subscription.get("type", "")).strip().lower() == "event"
                and str(subscription.get("provider", "")).strip().lower() == provider.name
                and bool(subscription.get("enabled", True))
            }
            if event_ids or team_ids or league_ids:
                provider_events = [
                    dict(event)
                    for event in provider.fetch_games(
                        event_ids=event_ids or None,
                        team_ids=team_ids or None,
                        league_ids=league_ids or None,
                    )
                ]
            else:
                provider_events = [dict(event) for event in provider.fetch_games()]
        except LookupError:
            self._json(HTTPStatus.NOT_FOUND, {"code": "provider_not_found", "error": "Sports provider is unavailable."})
            return
        except Exception:
            self._backend_unavailable()
            return
        events = []
        for event in provider_events:
            provider_event_id = str(event.get("provider_event_id", "")).strip()
            if not provider_event_id:
                continue
            event["requested"] = provider_event_id in requested_ids
            events.append(event)
        self._json(HTTPStatus.OK, {"events": events})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path not in {"/internal/v1/events/request", "/internal/v1/subscriptions"}:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if not self._require_auth():
            return
        payload = self._read_payload()
        if payload is None:
            return
        user_id = str(payload.get("user_id", "")).strip()
        provider_name = str(payload.get("provider", "")).strip()
        if parsed.path == "/internal/v1/events/request":
            subscription_type = "event"
            target_id = str(payload.get("provider_event_id", "")).strip()
        else:
            subscription_type = str(payload.get("type", "")).strip().lower()
            target_id = str(payload.get("provider_id", "")).strip()
        if not user_id or not provider_name or subscription_type not in {"event", "team", "league"} or not target_id:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "user_id, provider, valid type, and provider id are required."})
            return
        try:
            provider = _provider(provider_name)
            if subscription_type == "event":
                raw = provider.fetch_event(target_id)
                if raw is None:
                    raise KeyError
                normalized = provider.normalize_event(raw)
                name = str(normalized.get("name", "")).strip()
            elif subscription_type == "team":
                raw = provider.fetch_team(target_id)
                if raw is None:
                    raise KeyError
                name = self._safe_team(dict(raw))["name"]
            else:
                raw = provider.fetch_league(target_id)
                if raw is None:
                    raise KeyError
                name = self._safe_league(dict(raw))["name"]
            if not name:
                raise ValueError
            subscription, created = create_subscription(subscription_type, provider.name, target_id, name, user_id)
        except KeyError:
            self._json(HTTPStatus.NOT_FOUND, {"code": "sports_target_not_found", "error": "Sports target was not found."})
            return
        except LookupError:
            self._json(HTTPStatus.NOT_FOUND, {"code": "provider_not_found", "error": "Sports provider is unavailable."})
            return
        except ValueError:
            self._json(HTTPStatus.BAD_GATEWAY, {"error": "Sports provider returned an invalid target."})
            return
        except Exception:
            self._backend_unavailable()
            return
        self._json(HTTPStatus.OK, {"subscription": subscription, "created": created})

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        prefix = "/internal/v1/subscriptions/"
        if not parsed.path.startswith(prefix):
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if not self._require_auth():
            return
        atlas_subscription_id = urllib.parse.unquote(parsed.path[len(prefix):]).strip()
        params = urllib.parse.parse_qs(parsed.query, keep_blank_values=False)
        user_id = str(params.get("user_id", [""])[0]).strip()
        if not atlas_subscription_id or not user_id:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "subscription id and user_id are required."})
            return
        try:
            owned = any(
                str(item.get("subscription_id", "")).strip() == atlas_subscription_id
                for item in self._user_subscriptions(user_id)
            )
            if not owned:
                self._json(HTTPStatus.NOT_FOUND, {"error": "Sports subscription was not found."})
                return
            removed = remove_subscription(atlas_subscription_id)
        except Exception:
            self._backend_unavailable()
            return
        if not removed:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Sports subscription was not found."})
            return
        self._json(HTTPStatus.OK, {"removed": True})


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
