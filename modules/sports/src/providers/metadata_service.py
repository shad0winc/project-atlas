"""Authenticated writer metadata boundary. Inactive unless explicitly provisioned.

No provider registration, identity enrollment, playback lookup or health rewriting.
"""
from dataclasses import asdict
from datetime import date
from functools import lru_cache
import math
import os
from pathlib import Path
import threading
import time

from providers.espn_directory import MetadataTeam
from providers.espn_metadata import (
    ROUTES, Competition, MetadataEvent, Participant, _identifier, _text, _timestamp,
)
from providers.metadata_broker import (
    MetadataBroker, MetadataSnapshot, MetadataDirectorySnapshot, MetadataUnavailable,
)
from providers.metadata_store import MetadataStore

PATHS = {'/internal/v1/metadata/day': 'day', '/internal/v1/metadata/teams': 'teams',
         '/internal/v1/metadata/schedule': 'schedule'}
STATUSES = {'scheduled', 'live', 'final', 'postponed', 'cancelled', 'unknown'}
_factory_lock = threading.Lock()


def metadata_now():
    return time.time()


def validate_query(path, query):
    kind = PATHS[path]
    fields = ({'route', 'day'} if kind == 'day' else
              {'route', 'start_at', 'end_at'} if kind == 'schedule' else {'route'})
    if set(query) != fields or any(len(values) != 1 for values in query.values()):
        raise ValueError('Invalid metadata query')
    route = query['route'][0]
    if route not in ROUTES or (kind == 'teams' and ROUTES[route][2]):
        raise ValueError('Unsupported metadata route')
    day = None
    if kind == 'day':
        day = date.fromisoformat(query['day'][0])
        if day.isoformat() != query['day'][0]:
            raise ValueError('Invalid metadata date')
    if kind == 'schedule':
        from providers.metadata_schedule import schedule_days
        start_at, end_at = query['start_at'][0], query['end_at'][0]
        schedule_days(route, start_at, end_at, metadata_now())
        day = (start_at, end_at)
    return kind, route, day


@lru_cache(maxsize=1)
def _configured_broker(directory, settings=()):
    path = Path(directory)
    if not path.is_absolute():
        raise MetadataUnavailable('configuration')
    # Provisioning is an operator/deployment responsibility, never an HTTP side effect.
    return MetadataBroker(MetadataStore(path / 'metadata.sqlite'), **dict(settings))


def configured_broker(policy=None):
    directory = os.environ.get('ATLAS_SPORTS_METADATA_STATE_DIR', '')
    if not directory:
        raise MetadataUnavailable('disabled')
    settings=()
    if policy is None and os.environ.get('ATLAS_SPORTS_METADATA_REFRESH_FILE',''):
        from providers.metadata_refresh import load_refresh_policy, RefreshPolicyError
        try:
            policy=load_refresh_policy()
        except RefreshPolicyError:
            raise MetadataUnavailable('configuration') from None
        if policy is None:
            raise MetadataUnavailable('disabled')
    if policy is not None:
        settings=policy.broker_settings
    # lru_cache alone may construct twice on simultaneous first requests.
    with _factory_lock:
        return _configured_broker(directory,settings)


def query_metadata(path, query, *, broker_factory=configured_broker):
    kind, route, day = validate_query(path, query)
    broker = broker_factory()
    if kind == 'schedule':
        from providers.metadata_schedule import collect_schedule, schedule_document
        return schedule_document(collect_schedule(broker, route, *day, now=metadata_now()))
    snapshot = broker.fetch_day(route, day) if kind == 'day' else broker.fetch_teams(route)
    return snapshot_document(snapshot)


def snapshot_document(snapshot):
    result = asdict(snapshot)
    result['version'] = 1
    result['kind'] = 'day' if isinstance(snapshot, MetadataSnapshot) else 'teams'
    return result


def _fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError('Invalid metadata response fields')
    return value


def _stamp(value):
    if value is not None and _timestamp(value) != value:
        raise ValueError('Noncanonical metadata timestamp')
    return value


def _event(route, row):
    _fields(row, MetadataEvent.__dataclass_fields__)
    fight = ROUTES[route][2]
    if (row['provider'] != 'espn' or row['route'] != route
        or row['kind'] != ('fight_card' if fight else 'game')
        or row['status'] not in STATUSES):
        raise ValueError('Invalid event source identity')
    competitions = row['competitions']
    if not isinstance(competitions, list) or not 1 <= len(competitions) <= (100 if fight else 1):
        raise ValueError('Invalid competition list')
    parsed = []
    for competition in competitions:
        _fields(competition, Competition.__dataclass_fields__)
        people = competition['participants']
        if not isinstance(people, list) or len(people) != 2 or competition['status'] not in STATUSES:
            raise ValueError('Invalid competition')
        participants = []
        for person in people:
            _fields(person, Participant.__dataclass_fields__)
            if person['kind'] != ('athlete' if fight else 'team') or person['side'] not in ((None,) if fight else ('home', 'away')):
                raise ValueError('Invalid participant type')
            participants.append(Participant(_identifier(person['provider_id']), _text(person['name'], 'participant name'), person['side'], person['kind']))
        if len({person.provider_id for person in participants}) != 2 or (not fight and {person.side for person in participants} != {'home', 'away'}):
            raise ValueError('Invalid participant identities')
        parsed.append(Competition(_identifier(competition['provider_id']), _stamp(competition['start_at']), competition['status'], tuple(participants)))
    if len({c.provider_id for c in parsed}) != len(parsed):
        raise ValueError('Duplicate competition identity')
    return MetadataEvent('espn', route, _identifier(row['provider_event_id']), _text(row['name'], 'event name'), row['kind'], _stamp(row['start_at']), row['status'], tuple(parsed))


def parse_snapshot(document, *, kind, route, day=None, allow_stale=False):
    """Validate the private response independently of the HTTP peer and retain age."""
    common = {'version', 'kind', 'route', 'observed_at', 'expires_at', 'cache_hit', 'stale'}
    fields = common | ({'events', 'requested_day'} if kind == 'day' else {'teams'})
    _fields(document, fields)
    if (type(document['version']) is not int or document['version'] != 1
        or document['kind'] != kind or document['route'] != route or route not in ROUTES):
        raise ValueError('Metadata response identity mismatch')
    observed, expires = document['observed_at'], document['expires_at']
    if any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in (observed, expires)) or expires < observed or expires-observed > 3600:
        raise ValueError('Invalid metadata age')
    if any(type(document[field]) is not bool for field in ('cache_hit', 'stale')) or (document['stale'] and not allow_stale):
        raise ValueError('Fresh metadata response required')
    if kind == 'day':
        if type(day) is not date or document['requested_day'] != day.isoformat():
            raise ValueError('Metadata response date mismatch')
        rows = document['events']
        if not isinstance(rows, list) or len(rows) > 500:
            raise ValueError('Invalid event list')
        events = tuple(_event(route, row) for row in rows)
        if len({event.identity for event in events}) != len(events):
            raise ValueError('Duplicate event identity')
        return MetadataSnapshot(route, day.isoformat(), events, observed, expires, document['cache_hit'], document['stale'])
    if kind != 'teams' or ROUTES[route][2]:
        raise ValueError('Unsupported metadata directory')
    rows = document['teams']
    if not isinstance(rows, list) or not 1 <= len(rows) <= 500:
        raise ValueError('Invalid directory list')
    teams = []
    for row in rows:
        _fields(row, MetadataTeam.__dataclass_fields__)
        if row['route'] != route or not isinstance(row['abbreviation'], str) or len(row['abbreviation']) > 32:
            raise ValueError('Invalid directory source identity')
        teams.append(MetadataTeam(route, _identifier(row['team_id']), _text(row['name'], 'team name'), row['abbreviation']))
    if len({team.identity for team in teams}) != len(teams):
        raise ValueError('Duplicate team identity')
    return MetadataDirectorySnapshot(route, tuple(teams), observed, expires, document['cache_hit'], document['stale'])
