"""Private-writer ESPN discovery from fresh cached metadata only.

Deliberately absent from the background/playback provider registry. Public IDs
are source-scoped; no SportsDB aliases, playable sources or recording are added.
"""
from datetime import datetime, timedelta, timezone
import math

from providers.espn_directory import decode_entity_id, encode_entity_id
from providers.espn_metadata import ROUTES
from providers.metadata_broker import MetadataUnavailable
from providers.metadata_schedule import reconcile_schedule, schedule_days


def _iso(stamp):
    return datetime.fromtimestamp(stamp, timezone.utc).isoformat().replace('+00:00', 'Z')


class MetadataDiscoveryProvider:
    name = 'espn'

    def __init__(self, broker, routes):
        if (not isinstance(routes, tuple) or not routes or len(set(routes)) != len(routes)
            or any(route not in ROUTES for route in routes)):
            raise ValueError('Explicit supported metadata routes required')
        self.broker, self.routes = broker, routes

    def _route(self, route):
        if route not in self.routes:
            raise ValueError('Metadata route is not enabled')
        return route

    def _entity(self, value):
        route, native = decode_entity_id(value)
        return self._route(route), native

    @staticmethod
    def _query(query):
        if not isinstance(query, str) or len(query) > 128:
            raise ValueError('Invalid metadata discovery query')
        return query.strip().casefold()

    def _directory(self, route):
        evaluated, bucket = self.broker.read_teams(route)
        if bucket.status != 'fresh' or bucket.snapshot is None:
            raise MetadataUnavailable('discovery-directory', retry_after=bucket.retry_after_seconds)
        snapshot = bucket.snapshot
        if not snapshot.observed_at <= evaluated < snapshot.expires_at:
            raise MetadataUnavailable('discovery-directory-age')
        return snapshot.teams

    def _team(self, team):
        league, sport, _ = ROUTES[team.route]
        return {'id': team.public_id, 'name': team.name, 'sport': sport, 'league': league}

    def search_teams(self, query):
        query = self._query(query)
        if not query:
            return []
        rows = []
        for route in self.routes:
            if ROUTES[route][2]:
                continue
            rows.extend(self._team(team) for team in self._directory(route)
                        if query in (team.name + ' ' + team.abbreviation + ' ' + ROUTES[route][0]).casefold())
        return self._bounded(rows)

    def fetch_team(self, provider_id):
        route, native = self._entity(provider_id)
        if ROUTES[route][2]:
            raise ValueError('Fight participants are not followable teams')
        return next((self._team(team) for team in self._directory(route) if team.team_id == native), None)

    def fetch_league(self, provider_id):
        route = self._route(provider_id)
        league, sport, _ = ROUTES[route]
        return {'id': route, 'name': league, 'sport': sport, 'league': league}

    def search_leagues(self, query):
        query = self._query(query)
        if not query:
            return []
        return [self.fetch_league(route) for route in self.routes
                if query in (' '.join(ROUTES[route][:2]) + ' ' + route).casefold()]

    @staticmethod
    def _bounded(rows):
        if len(rows) > 500:
            raise MetadataUnavailable('discovery-response-budget')
        return rows

    def _schedule(self, route):
        now = self.broker.clock()
        if type(now) not in (int, float) or not math.isfinite(now) or now < 0:
            raise MetadataUnavailable('clock')
        today = datetime.fromtimestamp(now, timezone.utc).date()
        days = tuple(today + timedelta(days=offset) for offset in range(-1, 8))
        evaluated, buckets = self.broker.read_days(route, days)
        if datetime.fromtimestamp(evaluated, timezone.utc).date() != today:
            raise MetadataUnavailable('schedule-clock-rollover')
        if any(bucket.status != 'fresh' for bucket in buckets):
            raise MetadataUnavailable('discovery-schedule', retry_after=max(
                (bucket.retry_after_seconds for bucket in buckets), default=0))
        # Both bounded views use the SAME locked bucket snapshot. Reconciliation
        # precedes time/status filtering so old scheduled rows cannot survive a
        # newer cancellation, reschedule, unknown time or conflicting observation.
        start = datetime.combine(today-timedelta(days=1), datetime.min.time(), timezone.utc)
        windows = ((start.isoformat(), _iso(evaluated)),
                   (_iso(evaluated), _iso(evaluated+7*86400)))
        rows = {}
        for first, last in windows:
            wanted = {day.isoformat() for day in schedule_days(route, first, last, evaluated)[2]}
            view = reconcile_schedule(route, first, last, evaluated,
                                      tuple(bucket for bucket in buckets if bucket.requested_day in wanted))
            if view.conflicting_event_ids or view.unknown_time_event_ids:
                raise MetadataUnavailable('discovery-event-integrity')
            for row in view.events:
                if row.stale or not row.observed_at <= evaluated < row.expires_at:
                    raise MetadataUnavailable('discovery-event-age')
                rows[row.event.identity] = self._event(row)
        return self._bounded(list(rows.values()))

    @staticmethod
    def _event(row):
        event = row.event
        league, sport, fight = ROUTES[event.route]
        competitors = event.competitions[0].participants if not fight else ()
        teams = {person.side: encode_entity_id(event.route, person.provider_id)
                 for person in competitors}
        return {'provider': 'espn', 'provider_event_id': encode_entity_id(event.route, event.provider_event_id),
                'name': event.name, 'sport': sport, 'league': league,
                'provider_league_id': event.route, 'home_team_id': teams.get('home'),
                'away_team_id': teams.get('away'), 'start_at': event.start_at,
                'status': event.status, 'requested': False,
                'metadata_observed_at': _iso(row.observed_at),
                'metadata_expires_at': _iso(row.expires_at)}

    def fetch_games(self, *, event_ids=None, team_ids=None, league_ids=None, days_ahead=None):
        filters = []
        for values in (event_ids, team_ids, league_ids):
            if values is not None and (not isinstance(values, (list, tuple)) or len(values) > 64):
                raise ValueError('Invalid metadata discovery filters')
            filters.append(set(values or ()))
        events, teams, leagues = filters
        routes = {self._entity(value)[0] for value in events | teams}
        routes.update(self._route(value) for value in leagues)
        if not routes:
            routes = set(self.routes)
        if any(ROUTES[self._entity(value)[0]][2] for value in teams):
            raise ValueError('Fight participants are not followable teams')
        rows = []
        for route in self.routes:
            if route not in routes:
                continue
            for event in self._schedule(route):
                if (not any(filters) or event['provider_event_id'] in events
                    or event['home_team_id'] in teams or event['away_team_id'] in teams
                    or event['provider_league_id'] in leagues):
                    rows.append(event)
        return sorted(self._bounded(rows), key=lambda row: (row['start_at'], row['provider_event_id']))

    def fetch_event(self, provider_id):
        return next(iter(self.fetch_games(event_ids=[provider_id])), None)

    @staticmethod
    def normalize_event(event):
        if not isinstance(event, dict) or event.get('provider') != 'espn':
            raise ValueError('Invalid metadata event')
        return dict(event)

    def search_events(self, query):
        query = self._query(query)
        if not query:
            return []
        now = self.broker.clock()
        return [event for event in self.fetch_games()
                if (event['status'] == 'live' or (event['status'] == 'scheduled'
                    and datetime.fromisoformat(event['start_at'].replace('Z','+00:00')).timestamp() >= now))
                and query in (' '.join(event[key] for key in ('name','sport','league'))).casefold()]


def configured_discovery_provider():
    from providers.metadata_refresh import load_refresh_policy
    from providers.metadata_service import configured_broker
    policy = load_refresh_policy()
    if policy is None:
        raise MetadataUnavailable('disabled')
    return MetadataDiscoveryProvider(configured_broker(policy), policy.routes)
