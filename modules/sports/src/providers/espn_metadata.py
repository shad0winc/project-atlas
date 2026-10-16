"""Pure ESPN metadata preview parser. Not registered for production discovery.

No network, cache, state writes, playback URLs or SportsDB identity substitution.
Provider identity is scoped by route; assigning a durable Atlas owner is a separate
verified alias operation, never a fuzzy-name decision in this parser.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


class MetadataError(ValueError):
    """The response cannot be represented as a trustworthy schedule snapshot."""


# Deliberately bounded to the routes attested by the supplied response samples.
ROUTES = {
    "football/nfl": ("NFL", "Football", False),
    "basketball/nba": ("NBA", "Basketball", False),
    "baseball/mlb": ("MLB", "Baseball", False),
    "hockey/nhl": ("NHL", "Hockey", False),
    "soccer/eng.1": ("English Premier League", "Soccer", False),
    "mma/ufc": ("UFC", "MMA", True),
}


LEAGUE_UIDS = dict(zip(ROUTES, ("s:20~l:28", "s:40~l:46", "s:1~l:10",
                                     "s:70~l:90", "s:600~l:700", "s:3301~l:3321")))

def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise MetadataError(f"Invalid {label}")
    return value.strip()


def _identifier(value):
    value = _text(value, "identifier")
    if not value.isascii() or not value.isdecimal() or len(value) > 32:
        raise MetadataError("Invalid numeric provider identifier")
    return value


def _timestamp(value):
    if value is None:
        return None
    try:
        stamp = datetime.fromisoformat(_text(value, "timestamp").replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("Missing timezone")
        return stamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (ValueError, TypeError) as error:
        raise MetadataError("Invalid timestamp") from error


def _state(value):
    if not isinstance(value, dict) or not isinstance(value.get("type"), dict):
        return "unknown"
    row = value["type"]
    name = row.get("name")
    # Do not turn every pre-state or completed flag into playable/scheduled data.
    if name in {"STATUS_POSTPONED", "STATUS_DELAYED", "STATUS_SUSPENDED"}:
        return "postponed"
    if name in {"STATUS_CANCELED", "STATUS_CANCELLED"}:
        return "cancelled"
    if name == "STATUS_SCHEDULED" and row.get("state") == "pre" and row.get("completed") is False:
        return "scheduled"
    if name in {"STATUS_IN_PROGRESS", "STATUS_HALFTIME", "STATUS_END_PERIOD"} and row.get("state") == "in" and row.get("completed") is False:
        return "live"
    if name in {"STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_FINAL_OT", "STATUS_FINAL_SO"} and row.get("state") == "post" and row.get("completed") is True:
        return "final"
    return "unknown"


@dataclass(frozen=True)
class Participant:
    provider_id: str
    name: str
    side: str | None
    kind: str


@dataclass(frozen=True)
class Competition:
    provider_id: str
    start_at: str | None
    status: str
    participants: tuple[Participant, ...]


@dataclass(frozen=True)
class MetadataEvent:
    provider: str
    route: str
    provider_event_id: str
    name: str
    kind: str
    start_at: str | None
    status: str
    competitions: tuple[Competition, ...]

    @property
    def identity(self):
        return (self.provider, self.route, self.provider_event_id)

    @property
    def timing_kind(self):
        return "card_start" if self.kind == "fight_card" else "game_start"


def _competition(raw, fight):
    if not isinstance(raw, dict):
        raise MetadataError("Invalid competition")
    competitors = raw.get("competitors")
    if not isinstance(competitors, list) or len(competitors) != 2:
        raise MetadataError("Expected exactly two participants")
    people = []
    for row in competitors:
        if not isinstance(row, dict):
            raise MetadataError("Invalid participant")
        detail = row.get("athlete" if fight else "team")
        if not isinstance(detail, dict):
            raise MetadataError("Missing participant detail")
        if "id" in detail and _identifier(detail["id"]) != _identifier(row.get("id")):
            raise MetadataError("Participant identity mismatch")
        side = None if fight else row.get("homeAway")
        if not fight and side not in {"home", "away"}:
            raise MetadataError("Invalid team side")
        people.append(Participant(
            _identifier(row.get("id")),
            _text(detail.get("displayName"), "participant name"),
            side, "athlete" if fight else "team",
        ))
    if len({p.provider_id for p in people}) != 2:
        raise MetadataError("Duplicate participant")
    if not fight and {p.side for p in people} != {"home", "away"}:
        raise MetadataError("Missing distinct home and away teams")
    valid = raw.get("timeValid")
    if type(valid) is not bool:
        raise MetadataError("Missing explicit time validity")
    start = _timestamp(raw.get("date")) if valid else None
    return Competition(_identifier(raw.get("id")), start,
                       _state(raw.get("status")), tuple(people))


def parse_scoreboard(route, payload):
    """Parse one successful response; malformed data raises, an empty list stays empty.

    This does not attest full-league completeness or freshness. A caller must retain
    request outcome, provider observation time, request date and cache age separately.
    """
    if route not in ROUTES:
        raise MetadataError("Unsupported route")
    if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
        raise MetadataError("Missing events list")
    leagues = payload.get("leagues")
    if not isinstance(leagues, list) or len(leagues) != 1:
        raise MetadataError("Missing unambiguous league identity")
    if not isinstance(leagues[0], dict) or leagues[0].get("uid") != LEAGUE_UIDS[route]:
        raise MetadataError("Response league does not match requested route")
    if len(payload["events"]) > 500:
        raise MetadataError("Response event budget exceeded")
    fight = ROUTES[route][2]
    result = {}
    for raw in payload["events"]:
        if not isinstance(raw, dict):
            raise MetadataError("Invalid event")
        rows = raw.get("competitions")
        if not isinstance(rows, list) or not rows or len(rows) > 100:
            raise MetadataError("Invalid competition list")
        if not fight and len(rows) != 1:
            raise MetadataError("Ambiguous team event")
        competitions = tuple(_competition(row, fight) for row in rows)
        if len({c.provider_id for c in competitions}) != len(competitions):
            raise MetadataError("Duplicate competition")
        # A UFC parent date is card timing, never the main-card or broadcast time.
        start = _timestamp(raw.get("date")) if fight else competitions[0].start_at
        if fight and any(c.start_at is None for c in competitions):
            start = None
        event = MetadataEvent(
            "espn", route, _identifier(raw.get("id")),
            _text(raw.get("name"), "event name"),
            "fight_card" if fight else "game", start,
            _state(raw.get("status")), competitions,
        )
        earlier = result.get(event.identity)
        if earlier is not None and earlier != event:
            raise MetadataError("Conflicting duplicate event identity")
        result[event.identity] = event
    return tuple(result.values())
