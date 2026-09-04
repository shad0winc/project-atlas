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

from live_tv_bindings import (
    LiveTvBindingError,
    default_live_tv_binding_registry,
)
from live_sources import (
    LiveSourceCatalogError,
    load_live_source_catalog,
)
from providers.registry import enabled_providers
from source_lifecycle import (
    SourceLifecycleError,
    SourceLifecycleStore,
    SportsSource,
    rank_source_candidates,
)
from subscriptions import (
    create_subscription,
    load_subscriptions,
    normalize_subscription,
    remove_subscription,
    update_subscription_recording,
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


def _live_availability(
    provider: str,
    provider_event_id: str,
) -> dict[str, object]:
    source = load_live_source_catalog().for_event(
        provider,
        provider_event_id,
    )
    if source is None:
        return {
            "available": False,
            "atlas_channel_id": None,
        }

    atlas_channel_id = source.atlas_channel_id
    jellyfin_item_id = default_live_tv_binding_registry().resolve(
        atlas_channel_id
    )
    if jellyfin_item_id is None:
        return {
            "available": False,
            "atlas_channel_id": None,
        }

    return {
        "available": True,
        "atlas_channel_id": atlas_channel_id,
    }


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
    def _safe_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "provider": str(event.get("provider", "")).strip(),
            "provider_event_id": str(event.get("provider_event_id", "")).strip(),
            "name": str(event.get("name", "")).strip(),
            "sport": str(event.get("sport", "") or "").strip(),
            "league": str(event.get("league", "") or "").strip(),
            "start_at": event.get("start_at"),
            "status": str(event.get("status", "")).strip(),
            "requested": bool(event.get("requested", False)),
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

    @staticmethod
    def _source_store() -> SourceLifecycleStore:
        return SourceLifecycleStore()

    @staticmethod
    def _source_response(
        sources: tuple[SportsSource, ...],
    ) -> dict[str, Any]:
        return {
            "sources": [
                source.to_mapping()
                for source in sources
            ],
            "candidates": [
                candidate.to_mapping()
                for candidate
                in rank_source_candidates(sources)
            ],
        }

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

        params = urllib.parse.parse_qs(
            parsed.query,
            keep_blank_values=False,
        )

        if parsed.path == "/internal/v1/sources":
            try:
                sources = (
                    self._source_store().load()
                )
            except SourceLifecycleError:
                self._backend_unavailable()
                return

            self._json(
                HTTPStatus.OK,
                self._source_response(sources),
            )
            return

        user_id = str(
            params.get("user_id", [""])[0]
        ).strip()
        provider_name = str(params.get("provider", ["thesportsdb"])[0]).strip()

        if parsed.path == "/internal/v1/live/availability":
            provider_event_id = str(
                params.get("provider_event_id", [""])[0]
            ).strip()
            if not provider_name or not provider_event_id:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "error": (
                            "provider and provider_event_id are required."
                        )
                    },
                )
                return
            try:
                availability = _live_availability(
                    provider_name,
                    provider_event_id,
                )
            except (LiveSourceCatalogError, LiveTvBindingError):
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "code": "sports_live_availability_unavailable",
                        "error": "Sports live availability is unavailable.",
                    },
                )
                return
            self._json(
                HTTPStatus.OK,
                {"availability": availability},
            )
            return

        if parsed.path == "/internal/v1/sources":
            try:
                source = SportsSource.from_mapping(
                    payload
                )

                store = self._source_store()
                sources = store.load()

                if any(
                    item.source_id
                    == source.source_id
                    for item in sources
                ):
                    self._json(
                        HTTPStatus.CONFLICT,
                        {
                            "code": (
                                "sports_source_exists"
                            ),
                            "error": (
                                "Sports source "
                                "already exists."
                            ),
                        },
                    )
                    return

                updated = (
                    *sources,
                    source,
                )

                store.write(updated)

            except SourceLifecycleError as exc:
                self._json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {
                        "code": (
                            "sports_source_invalid"
                        ),
                        "error": str(exc),
                    },
                )
                return

            self._json(
                HTTPStatus.CREATED,
                {
                    "source": (
                        source.to_mapping()
                    ),
                    **self._source_response(
                        tuple(updated)
                    ),
                },
            )
            return

        if parsed.path == "/internal/v1/live-tv/bindings":
            registry = default_live_tv_binding_registry()
            atlas_channel_id = str(
                params.get("atlas_channel_id", [""])[0]
            ).strip()
            try:
                if atlas_channel_id:
                    jellyfin_item_id = registry.resolve(
                        atlas_channel_id
                    )
                    if jellyfin_item_id is None:
                        self._json(
                            HTTPStatus.NOT_FOUND,
                            {
                                "code": "sports_live_tv_binding_not_found",
                                "error": "Live TV binding was not found.",
                            },
                        )
                        return
                    self._json(
                        HTTPStatus.OK,
                        {
                            "binding": {
                                "atlas_channel_id": atlas_channel_id,
                                "jellyfin_item_id": jellyfin_item_id,
                            }
                        },
                    )
                    return

                self._json(
                    HTTPStatus.OK,
                    {
                        "bindings": [
                            binding.safe_dict()
                            for binding in registry.list_bindings()
                        ]
                    },
                )
            except LiveTvBindingError:
                self._json(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    {
                        "code": "sports_live_tv_binding_state_invalid",
                        "error": "Live TV binding state is invalid.",
                    },
                )
            return

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

        if parsed.path in {
            "/internal/v1/search/teams",
            "/internal/v1/search/leagues",
            "/internal/v1/search/events",
        }:
            query = str(params.get("query", [""])[0]).strip()
            if not query or not provider_name:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "query and provider are required."})
                return
            if parsed.path.endswith("/events") and not user_id:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "user_id is required for event search."})
                return
            try:
                provider = _provider(provider_name)
                if parsed.path.endswith("/teams"):
                    raw = provider.search_teams(query)
                    results = [self._safe_team(dict(item)) for item in raw if isinstance(item, dict)]
                    results = [item for item in results if item["id"] and item["name"]]
                    self._json(HTTPStatus.OK, {"teams": results})
                elif parsed.path.endswith("/leagues"):
                    raw = provider.search_leagues(query)
                    results = [self._safe_league(dict(item)) for item in raw if isinstance(item, dict)]
                    results = [item for item in results if item["id"] and item["name"]]
                    self._json(HTTPStatus.OK, {"leagues": results})
                else:
                    requested_ids = {
                        str(subscription.get("id", "")).strip()
                        for subscription in self._user_subscriptions(user_id)
                        if str(subscription.get("type", "")).strip().lower() == "event"
                        and str(subscription.get("provider", "")).strip().lower() == provider.name
                        and bool(subscription.get("enabled", True))
                    }
                    raw = provider.search_events(query)
                    results = []
                    for item in raw:
                        if not isinstance(item, dict):
                            continue
                        event = dict(item)
                        provider_event_id = str(event.get("provider_event_id", "")).strip()
                        if not provider_event_id:
                            continue
                        event["requested"] = provider_event_id in requested_ids
                        results.append(self._safe_event(event))
                    self._json(HTTPStatus.OK, {"events": results})
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
            events.append(self._safe_event(event))
        self._json(HTTPStatus.OK, {"events": events})

    def do_POST(self) -> None:
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path not in {
            "/internal/v1/events/request",
            "/internal/v1/subscriptions",
            "/internal/v1/live-tv/bindings",
            "/internal/v1/sources",
        }:
            self._json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return
        if not self._require_auth():
            return
        payload = self._read_payload()
        if payload is None:
            return

        if parsed.path == "/internal/v1/live-tv/bindings":
            atlas_channel_id = str(
                payload.get("atlas_channel_id", "")
            ).strip()
            jellyfin_item_id = str(
                payload.get("jellyfin_item_id", "")
            ).strip()
            if not atlas_channel_id or not jellyfin_item_id:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "error": (
                            "atlas_channel_id and jellyfin_item_id "
                            "are required."
                        )
                    },
                )
                return
            try:
                binding = default_live_tv_binding_registry().set(
                    atlas_channel_id,
                    jellyfin_item_id,
                )
            except LiveTvBindingError:
                self._json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {
                        "code": "sports_live_tv_binding_invalid",
                        "error": "Live TV binding is invalid.",
                    },
                )
                return
            self._json(
                HTTPStatus.OK,
                {"binding": binding.safe_dict()},
            )
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

    def do_PATCH(self) -> None:
        parsed = urllib.parse.urlsplit(
            self.path
        )

        source_prefix = (
            "/internal/v1/sources/"
        )

        if parsed.path.startswith(
            source_prefix
        ):
            if not self._require_auth():
                return

            source_id = urllib.parse.unquote(
                parsed.path[
                    len(source_prefix):
                ]
            ).strip()

            if not source_id:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "error": (
                            "source_id is required."
                        )
                    },
                )
                return

            payload = self._read_payload()

            if payload is None:
                return

            try:
                store = self._source_store()
                sources = store.load()

                current = next(
                    (
                        item
                        for item in sources
                        if item.source_id
                        == source_id
                    ),
                    None,
                )

                if current is None:
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {
                            "code": (
                                "sports_source_not_found"
                            ),
                            "error": (
                                "Sports source "
                                "was not found."
                            ),
                        },
                    )
                    return

                if (
                    "source_id" in payload
                    and str(
                        payload["source_id"]
                    ).strip()
                    != source_id
                ):
                    raise SourceLifecycleError(
                        "source_id cannot "
                        "be changed"
                    )

                merged = (
                    current.to_mapping()
                )

                merged.update(payload)
                merged["source_id"] = (
                    source_id
                )

                updated_source = (
                    SportsSource.from_mapping(
                        merged
                    )
                )

                updated = tuple(
                    updated_source
                    if item.source_id
                    == source_id
                    else item
                    for item in sources
                )

                store.write(updated)

            except SourceLifecycleError as exc:
                self._json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {
                        "code": (
                            "sports_source_invalid"
                        ),
                        "error": str(exc),
                    },
                )
                return

            self._json(
                HTTPStatus.OK,
                {
                    "source": (
                        updated_source
                        .to_mapping()
                    ),
                    **self._source_response(
                        updated
                    ),
                },
            )
            return

        prefix = "/internal/v1/subscriptions/"
        suffix = "/recording"

        if not (
            parsed.path.startswith(prefix)
            and parsed.path.endswith(suffix)
        ):
            self._json(
                HTTPStatus.NOT_FOUND,
                {"error": "Not found."},
            )
            return

        if not self._require_auth():
            return

        atlas_subscription_id = urllib.parse.unquote(
            parsed.path[
                len(prefix) : -len(suffix)
            ]
        ).strip()

        payload = self._read_payload()
        if payload is None:
            return

        user_id = str(
            payload.get("user_id", "")
        ).strip()
        record = payload.get("record")

        if (
            not atlas_subscription_id
            or not user_id
            or not isinstance(record, bool)
        ):
            self._json(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": (
                        "subscription id, user_id, and boolean record "
                        "are required."
                    )
                },
            )
            return

        try:
            updated = update_subscription_recording(
                atlas_subscription_id,
                user_id,
                record,
            )
        except ValueError as exc:
            self._json(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {
                    "code": "sports_recording_target_unsupported",
                    "error": str(exc),
                },
            )
            return
        except Exception:
            self._backend_unavailable()
            return

        if updated is None:
            self._json(
                HTTPStatus.NOT_FOUND,
                {
                    "code": "sports_subscription_not_found",
                    "error": (
                        "Sports subscription was not found."
                    ),
                },
            )
            return

        self._json(
            HTTPStatus.OK,
            {"subscription": updated},
        )

    def do_DELETE(self) -> None:
        parsed = urllib.parse.urlsplit(
            self.path
        )

        source_prefix = (
            "/internal/v1/sources/"
        )

        if parsed.path.startswith(
            source_prefix
        ):
            if not self._require_auth():
                return

            source_id = urllib.parse.unquote(
                parsed.path[
                    len(source_prefix):
                ]
            ).strip()

            if not source_id:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {
                        "error": (
                            "source_id is required."
                        )
                    },
                )
                return

            try:
                store = self._source_store()
                sources = store.load()

                updated = tuple(
                    item
                    for item in sources
                    if item.source_id
                    != source_id
                )

                if (
                    len(updated)
                    == len(sources)
                ):
                    self._json(
                        HTTPStatus.NOT_FOUND,
                        {
                            "code": (
                                "sports_source_not_found"
                            ),
                            "error": (
                                "Sports source "
                                "was not found."
                            ),
                        },
                    )
                    return

                store.write(updated)

            except SourceLifecycleError:
                self._backend_unavailable()
                return

            self._json(
                HTTPStatus.OK,
                {
                    "removed": True,
                    "source_id": source_id,
                    **self._source_response(
                        updated
                    ),
                },
            )
            return

        binding_prefix = (
            "/internal/v1/live-tv/bindings/"
        )
        if parsed.path.startswith(binding_prefix):
            if not self._require_auth():
                return
            atlas_channel_id = urllib.parse.unquote(
                parsed.path[len(binding_prefix):]
            ).strip()
            if not atlas_channel_id:
                self._json(
                    HTTPStatus.BAD_REQUEST,
                    {"error": "atlas_channel_id is required."},
                )
                return
            try:
                removed = default_live_tv_binding_registry().delete(
                    atlas_channel_id
                )
            except LiveTvBindingError:
                self._json(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    {
                        "code": "sports_live_tv_binding_invalid",
                        "error": "Live TV binding is invalid.",
                    },
                )
                return
            if not removed:
                self._json(
                    HTTPStatus.NOT_FOUND,
                    {
                        "code": "sports_live_tv_binding_not_found",
                        "error": "Live TV binding was not found.",
                    },
                )
                return
            self._json(HTTPStatus.OK, {"removed": True})
            return

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

    default_live_tv_binding_registry().ensure()
    SourceLifecycleStore().ensure()

    server = ThreadingHTTPServer(
        (args.host, args.port),
        Handler,
    )
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
