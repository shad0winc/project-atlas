"""Curated competition browsing over existing snapshots, with no fetch surface.

This reader never constructs MetadataStore/MetadataBroker or imports a provider
registry. Missing configuration/state is reported rather than provisioned.
Refresh remains a separate explicitly configured writer-owned worker.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import time

from providers.espn_metadata import ROUTES, parse_scoreboard
from providers.espn_directory import parse_team_directory, encode_entity_id
from providers.metadata_broker import MetadataDayCache, MetadataSnapshot, MetadataDirectorySnapshot
from providers.metadata_schedule import reconcile_schedule, schedule_days

COMPETITIONS = (
    ('nfl', 'American football', 'NFL', 'football/nfl'),
    ('college-football', 'American football', 'College football', None),
    ('nba', 'Basketball', 'NBA', 'basketball/nba'),
    ('college-basketball', 'Basketball', 'College basketball', None),
    ('mlb', 'Baseball', 'MLB', 'baseball/mlb'),
    ('nhl', 'Hockey', 'NHL', 'hockey/nhl'),
    ('premier-league', 'Soccer', 'English Premier League', 'soccer/eng.1'),
    ('ufc', 'Combat sports', 'UFC', 'mma/ufc'),
)
MAX_AGE = 86400
MAX_PAYLOAD = 4_000_000


class CuratedUnavailable(RuntimeError):
    pass


def iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace('+00:00', 'Z')


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid, info.st_nlink)


class SnapshotReader:
    """One read-only SQLite snapshot for each browser operation."""
    def __init__(self, directory, *, clock=time.time):
        self.directory = Path(directory)
        self.clock = clock

    def _verify(self):
        directory = self.directory
        if not directory.is_absolute() or directory.resolve(strict=True) != directory:
            raise CuratedUnavailable('cache-path')
        info = directory.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
            raise CuratedUnavailable('cache-directory')
        path = directory / 'metadata.sqlite'
        if path.resolve(strict=True) != path:
            raise CuratedUnavailable('cache-path')
        database = path.lstat()
        if (not stat.S_ISREG(database.st_mode) or database.st_uid != os.geteuid()
                or database.st_nlink != 1 or database.st_mode & 0o077):
            raise CuratedUnavailable('cache-file')
        return path, identity(info), identity(database)

    @contextmanager
    def snapshot(self):
        path, directory_pin, file_pin = self._verify()
        now = self.clock()
        if not finite(now):
            raise CuratedUnavailable('clock')
        db = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=2)
        try:
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            if db.execute('SELECT version FROM metadata_schema').fetchall() != [(1,)]:
                raise CuratedUnavailable('cache-schema')
            yield db, now
            _, directory_after, file_after = self._verify()
            if directory_after != directory_pin or file_after != file_pin:
                raise CuratedUnavailable('cache-replaced')
        finally:
            db.close()

    @staticmethod
    def bucket(db, route, day, now):
        holds = db.execute('SELECT until_stamp FROM metadata_holds WHERE key IN (?,?)',
                           ('espn:cooldown', route + ':' + day)).fetchall()
        if any(not finite(row[0]) for row in holds):
            raise CuratedUnavailable('cache-hold')
        retry = min(3600, max(0, math.ceil(max((row[0] for row in holds), default=now) - now)))
        row = db.execute('SELECT payload,observed,expires FROM metadata_cache WHERE route=? AND day=?', (route, day)).fetchone()
        if row is None:
            return MetadataDayCache(day, None, 'missing', retry)
        payload, observed, expires = row
        if (not finite(observed) or not finite(expires) or observed > now
                or not 0 < expires - observed <= 3600 or not isinstance(payload, str)
                or len(payload.encode()) > MAX_PAYLOAD):
            return MetadataDayCache(day, None, 'invalid', retry)
        if now - observed > MAX_AGE:
            return MetadataDayCache(day, None, 'stale', retry)
        try:
            document = json.loads(payload, object_pairs_hook=unique)
            stale = expires <= now
            if day == '@teams':
                values = parse_team_directory(route, document)
                snapshot = MetadataDirectorySnapshot(route, values, observed, expires, True, stale)
            else:
                values = parse_scoreboard(route, document)
                snapshot = MetadataSnapshot(route, day, values, observed, expires, True, stale)
        except (ValueError, TypeError, KeyError):
            return MetadataDayCache(day, None, 'invalid', retry)
        return MetadataDayCache(day, snapshot, 'stale' if stale else 'fresh', retry)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate snapshot field')
        result[key] = value
    return result


def outcome(buckets):
    if any(row.status == 'invalid' for row in buckets):
        return 'unavailable'
    if all(row.status == 'fresh' for row in buckets):
        return 'ready'
    if all(row.snapshot is None for row in buckets):
        return 'preparing' if all(row.status == 'missing' for row in buckets) else 'stale'
    if all(row.status in ('fresh', 'stale') for row in buckets):
        return 'stale'
    return 'partial'


class CuratedSchedules:
    def __init__(self, *, enabled=False, routes=(), reader=None, clock=time.time):
        if type(enabled) is not bool or not isinstance(routes, tuple) or len(set(routes)) != len(routes) or any(route not in ROUTES for route in routes):
            raise ValueError('Invalid curated schedule configuration')
        self.enabled, self.routes, self.reader, self.clock = enabled, routes, reader, clock

    def _now(self):
        now = self.clock()
        if not finite(now):
            raise CuratedUnavailable('clock')
        return now

    def _competition(self, key):
        if not isinstance(key, str) or len(key) > 64:
            raise ValueError('Invalid competition')
        return next((row for row in COMPETITIONS if row[0] == key), None)

    def catalog(self):
        now = self._now()
        return {'version': 1, 'enabled': self.enabled, 'evaluated_at': iso(now),
                'competitions': [{'id': key, 'sport': sport, 'name': name, 'provider': 'espn',
                    'provider_league_id': route, 'team_directory_supported': bool(route and not ROUTES[route][2]),
                    'status': 'unsupported' if route is None else 'configured' if self.enabled and route in self.routes else 'disabled'}
                    for key, sport, name, route in COMPETITIONS]}

    def teams(self, key):
        competition = self._competition(key)
        if competition is None:
            raise ValueError('Unknown competition')
        now = self._now()
        route = competition[3]
        result = {'version': 1, 'competition_id': key, 'provider': 'espn',
                  'provider_league_id': route, 'evaluated_at': iso(now), 'status': 'disabled',
                  'observed_at': None, 'expires_at': None, 'retry_after_seconds': 0, 'teams': []}
        if route is None or ROUTES[route][2]:
            return {**result, 'status': 'unsupported'}
        if not self.enabled or route not in self.routes:
            return result
        if self.reader is None:
            return {**result, 'status': 'preparing'}
        try:
            with self.reader.snapshot() as (db, evaluated):
                bucket = self.reader.bucket(db, route, '@teams', evaluated)
                result.update(evaluated_at=iso(evaluated), status=outcome((bucket,)), retry_after_seconds=bucket.retry_after_seconds)
                if bucket.snapshot:
                    snapshot = bucket.snapshot
                    result.update(observed_at=iso(snapshot.observed_at), expires_at=iso(snapshot.expires_at),
                        teams=[{'id': team.public_id, 'name': team.name} for team in sorted(snapshot.teams, key=lambda team: (team.name.casefold(), team.team_id))])
        except FileNotFoundError:
            result.update(status='preparing', teams=[], observed_at=None, expires_at=None)
        except (CuratedUnavailable, sqlite3.Error, OSError, ValueError):
            result.update(status='unavailable', teams=[], observed_at=None, expires_at=None)
        return result

    def schedule(self, key, start_at, end_at):
        competition = self._competition(key)
        if competition is None:
            raise ValueError('Unknown competition')
        route = competition[3]
        now = self._now()
        if route is None:
            raise ValueError('Unsupported competition')
        start, end, days = schedule_days(route, start_at, end_at, now)
        result = {'version': 1, 'competition_id': key, 'provider': 'espn', 'provider_league_id': route,
                  'start_at': iso(start.timestamp()), 'end_at': iso(end.timestamp()), 'evaluated_at': iso(now),
                  'status': 'disabled', 'coverage_complete': False, 'provider_completeness_proven': False,
                  'required_buckets': len(days), 'fresh_buckets': 0, 'retry_after_seconds': 0,
                  'observed_at': None, 'expires_at': None, 'events': []}
        if not self.enabled or route not in self.routes:
            return result
        if self.reader is None:
            return {**result, 'status': 'preparing'}
        try:
            with self.reader.snapshot() as (db, evaluated):
                if schedule_days(route, start_at, end_at, evaluated)[2] != days:
                    raise CuratedUnavailable('clock-rollover')
                buckets = tuple(self.reader.bucket(db, route, day.isoformat(), evaluated) for day in days)
                schedule = reconcile_schedule(route, start_at, end_at, evaluated, buckets)
                state = outcome(buckets)
                if schedule.conflicting_event_ids or schedule.unknown_time_event_ids:
                    state = 'partial'
                result.update(evaluated_at=iso(evaluated), status=state, coverage_complete=state == 'ready',
                    fresh_buckets=sum(bucket.status == 'fresh' for bucket in buckets),
                    retry_after_seconds=max((bucket.retry_after_seconds for bucket in buckets), default=0))
                snapshots = [bucket.snapshot for bucket in buckets if bucket.snapshot]
                if snapshots:
                    result.update(observed_at=iso(min(row.observed_at for row in snapshots)),
                                  expires_at=iso(min(row.expires_at for row in snapshots)))
                for row in schedule.events:
                    event = row.event
                    league, sport, fight = ROUTES[route]
                    people = event.competitions[0].participants if not fight else ()
                    teams = {person.side: encode_entity_id(route, person.provider_id) for person in people}
                    result['events'].append({'provider': 'espn', 'provider_event_id': encode_entity_id(route, event.provider_event_id),
                        'name': event.name, 'sport': sport, 'league': league, 'provider_league_id': route,
                        'home_team_id': teams.get('home'), 'away_team_id': teams.get('away'),
                        'start_at': event.start_at, 'status': event.status, 'requested': False,
                        'metadata_observed_at': iso(row.observed_at), 'metadata_expires_at': iso(row.expires_at)})
                if len(result['events']) > 500 or len(json.dumps(result).encode()) > MAX_PAYLOAD:
                    raise CuratedUnavailable('response-budget')
        except FileNotFoundError:
            result.update(status='preparing', events=[], coverage_complete=False, observed_at=None, expires_at=None, fresh_buckets=0)
        except (CuratedUnavailable, sqlite3.Error, OSError, ValueError):
            result.update(status='unavailable', events=[], coverage_complete=False, observed_at=None, expires_at=None, fresh_buckets=0)
        return result


def configured_curated_schedules():
    value = os.getenv('ATLAS_SPORTS_CURATED_BROWSE_ENABLED', '0')
    if value not in {'0', '1'}:
        raise CuratedUnavailable('configuration')
    if value == '0':
        return CuratedSchedules()
    from providers.metadata_refresh import load_refresh_policy
    policy = load_refresh_policy()
    directory = os.getenv('ATLAS_SPORTS_METADATA_STATE_DIR', '')
    return CuratedSchedules(enabled=True, routes=policy.routes if policy else (),
                            reader=SnapshotReader(directory) if directory else None)
