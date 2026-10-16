"""Bounded cache-only schedule collection with explicit bucket coverage.

This is metadata, never a playable-source or upstream-completeness assertion.
"""
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import json
import math

from providers.espn_metadata import ROUTES, MetadataEvent
from providers.metadata_broker import MetadataDayCache, MetadataUnavailable


@dataclass(frozen=True)
class ScheduleEvent:
    event: MetadataEvent
    observed_at: float
    expires_at: float
    stale: bool


@dataclass(frozen=True)
class MetadataSchedule:
    route: str
    start_at: str
    end_at: str
    evaluated_at: float
    buckets: tuple[MetadataDayCache, ...]
    events: tuple[ScheduleEvent, ...]
    conflicting_event_ids: tuple[str, ...]
    unknown_time_event_ids: tuple[str, ...]

    @property
    def all_buckets_fresh(self):
        return all(bucket.status == 'fresh' for bucket in self.buckets)

    @property
    def outcome(self):
        if not self.all_buckets_fresh or self.conflicting_event_ids or self.unknown_time_event_ids:
            return 'partial'
        return 'events' if self.events else 'empty'

    def upcoming(self, now):
        return tuple(replace(row, stale=row.stale or row.expires_at <= now)
                     for row in self.events if row.event.status == 'scheduled'
                     and _aware(row.event.start_at).timestamp() >= now)

    def fresh_live(self, now):
        return tuple(row for row in self.events if not row.stale
                     and row.observed_at <= now < row.expires_at
                     and row.event.status == 'live'
                     and _aware(row.event.start_at).timestamp() <= now)


def _aware(value):
    if not isinstance(value, str):
        raise ValueError('Aware schedule timestamp required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('Aware schedule timestamp required')
    return parsed.astimezone(timezone.utc)


def _iso(value):
    return value.isoformat().replace('+00:00', 'Z')


def schedule_days(route, start_at, end_at, now):
    if route not in ROUTES or type(now) not in (int,float) or not math.isfinite(now) or now < 0:
        raise ValueError('Invalid schedule request')
    start, end = _aware(start_at), _aware(end_at)
    if not 0 < (end-start).total_seconds() <= 7*86400:
        raise ValueError('Schedule window must be positive and at most seven days')
    today = datetime.fromtimestamp(now, timezone.utc).date()
    if start.date() < today-timedelta(days=1) or end.date() > today+timedelta(days=7):
        raise ValueError('Schedule request outside bounded horizon')
    # Provider scoreboard dates are calendar buckets, not guaranteed UTC dates.
    # Include the prior bucket where permitted, then filter aware event timestamps.
    first = max(start.date()-timedelta(days=1), today-timedelta(days=1))
    last = end.date()
    days = tuple(first+timedelta(days=offset) for offset in range((last-first).days+1))
    if not 1 <= len(days) <= 9:
        raise ValueError('Schedule bucket budget exceeded')
    return start, end, days


def collect_schedule(broker, route, start_at, end_at, *, now):
    start, end, days = schedule_days(route, start_at, end_at, now)
    evaluated, buckets = broker.read_days(route, days)
    # A midnight rollover between validation and the locked read must not silently
    # select a different set of dates.
    if schedule_days(route, start_at, end_at, evaluated)[2] != days:
        raise MetadataUnavailable('schedule-clock-rollover')
    return reconcile_schedule(route, _iso(start), _iso(end), evaluated, buckets)


def reconcile_schedule(route, start_at, end_at, evaluated_at, buckets):
    start, end, days = schedule_days(route, start_at, end_at, evaluated_at)
    if tuple(bucket.requested_day for bucket in buckets) != tuple(day.isoformat() for day in days):
        raise ValueError('Schedule bucket coverage mismatch')
    candidates = {}
    for bucket in buckets:
        snapshot = bucket.snapshot
        if snapshot is None:
            continue
        if snapshot.route != route or snapshot.requested_day != bucket.requested_day:
            raise ValueError('Schedule source identity mismatch')
        for event in snapshot.events:
            if event.route != route:
                raise ValueError('Schedule event route mismatch')
            candidates.setdefault(event.identity, []).append((snapshot, event))
    selected, conflicts, undated = [], [], []
    for identity, observations in candidates.items():
        newest = max(snapshot.observed_at for snapshot,event in observations)
        latest = [(snapshot,event) for snapshot,event in observations if snapshot.observed_at == newest]
        event = latest[0][1]
        if any(other != event for snapshot,other in latest):
            conflicts.append(identity[2])
            continue
        # Resolve revisions BEFORE filtering: an old scheduled time cannot survive
        # a newer cancellation, final status or move outside the requested window.
        if event.start_at is None:
            undated.append(identity[2])
            continue
        if not start <= _aware(event.start_at) < end:
            continue
        observed, _ = min(latest, key=lambda row: row[0].expires_at)
        selected.append(ScheduleEvent(event, newest, observed.expires_at,
                                     observed.stale or observed.expires_at <= evaluated_at))
    selected.sort(key=lambda row: (_aware(row.event.start_at), row.event.provider_event_id))
    return MetadataSchedule(route, _iso(start), _iso(end), evaluated_at, tuple(buckets),
                            tuple(selected), tuple(sorted(conflicts)), tuple(sorted(undated)))


def schedule_document(schedule):
    from providers.metadata_service import snapshot_document
    document = {
        'version': 1, 'kind': 'schedule', 'route': schedule.route,
        'start_at': schedule.start_at, 'end_at': schedule.end_at,
        'evaluated_at': schedule.evaluated_at,
        'buckets': [{'requested_day': row.requested_day, 'status': row.status,
                     'retry_after_seconds': row.retry_after_seconds,
                     'snapshot': snapshot_document(row.snapshot) if row.snapshot else None}
                    for row in schedule.buckets],
    }
    if len(json.dumps(document, separators=(',',':'), allow_nan=False).encode()) > 4_000_000:
        raise MetadataUnavailable('schedule-response-budget')
    return document


def parse_schedule(document, *, route, start_at, end_at):
    from providers.metadata_service import _fields, parse_snapshot
    _fields(document, {'version','kind','route','start_at','end_at','evaluated_at','buckets'})
    if type(document['version']) is not int or document['version'] != 1 or document['kind'] != 'schedule' or document['route'] != route:
        raise ValueError('Schedule response identity mismatch')
    evaluated = document['evaluated_at']
    start,end,days = schedule_days(route, start_at, end_at, evaluated)
    if document['start_at'] != _iso(start) or document['end_at'] != _iso(end):
        raise ValueError('Schedule response window mismatch')
    rows = document['buckets']
    if not isinstance(rows,list) or len(rows) != len(days):
        raise ValueError('Schedule response bucket mismatch')
    buckets=[]
    for row, day in zip(rows,days):
        _fields(row, {'requested_day','status','retry_after_seconds','snapshot'})
        if row['requested_day'] != day.isoformat() or type(row['retry_after_seconds']) is not int or not 0 <= row['retry_after_seconds'] <= 3600:
            raise ValueError('Invalid schedule bucket')
        snapshot = None
        if row['status'] in {'fresh','stale'}:
            snapshot = parse_snapshot(row['snapshot'], kind='day', route=route, day=day, allow_stale=True)
            expected_stale = snapshot.expires_at <= evaluated
            if snapshot.observed_at > evaluated or snapshot.stale != expected_stale or (row['status']=='stale') != expected_stale:
                raise ValueError('Invalid schedule observation age')
        elif row['status'] not in {'missing','invalid'} or row['snapshot'] is not None:
            raise ValueError('Invalid schedule bucket status')
        buckets.append(MetadataDayCache(day.isoformat(),snapshot,row['status'],row['retry_after_seconds']))
    return reconcile_schedule(route, _iso(start), _iso(end), evaluated, tuple(buckets))


def refresh_one_schedule_day(broker, route, start_at, end_at, *, now):
    """Explicit background primitive: at most one upstream admission per call.

    A caller must schedule/back off this operation. Cache-only HTTP reads never
    invoke it. Shared broker reservations still arbitrate concurrent consumers.
    """
    schedule = collect_schedule(broker, route, start_at, end_at, now=now)
    today = datetime.fromtimestamp(schedule.evaluated_at, timezone.utc).date().isoformat()
    pending = [row for row in schedule.buckets
               if row.status != 'fresh' and row.retry_after_seconds == 0]
    if not pending:
        return None
    pending.sort(key=lambda row: (row.requested_day != today,
        row.snapshot.expires_at if row.snapshot else -1, row.requested_day))
    from datetime import date
    return broker.fetch_day(route, date.fromisoformat(pending[0].requested_day))


def reevaluate_schedule(schedule, now):
    """Age a delivered cache view without renewing any provider observation."""
    if type(now) not in (int,float) or not math.isfinite(now) or now < schedule.evaluated_at:
        raise ValueError('Invalid schedule evaluation clock')
    rows=[]
    for bucket in schedule.buckets:
        snapshot=bucket.snapshot
        if snapshot is not None and snapshot.expires_at <= now and not snapshot.stale:
            snapshot=replace(snapshot, stale=True)
            bucket=replace(bucket, snapshot=snapshot, status='stale')
        rows.append(bucket)
    return reconcile_schedule(schedule.route, schedule.start_at, schedule.end_at, now, tuple(rows))
