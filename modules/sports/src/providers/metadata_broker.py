"""Inactive ESPN metadata client/cache. Construct only in the private Sports writer.

No default instance, provider registration, runtime path or API route is installed.
"""
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from providers.espn_metadata import MetadataError, ROUTES, parse_scoreboard


class MetadataUnavailable(RuntimeError):
    def __init__(self, category, *, retry_after=0, http_status=None):
        self.category = category
        self.retry_after = retry_after
        self.http_status = http_status
        super().__init__('Independent Sports metadata is unavailable: ' + category)


def retry_after_seconds(value, now):
    try:
        seconds = float(value)
        if not math.isfinite(seconds):
            raise ValueError()
    except (ValueError, TypeError):
        try:
            stamp = parsedate_to_datetime(value)
            if stamp.tzinfo is None:
                raise ValueError()
            seconds = stamp.timestamp() - now
        except (ValueError, TypeError, OverflowError, AttributeError):
            seconds = 60
    return max(1, min(3600, math.ceil(seconds)))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate metadata JSON key')
        result[key] = value
    return result


class ESPNDayTransport:
    def __init__(self, *, opener=None, clock=time.time):
        # Normal urllib proxy/environment handling is preserved. No proxy values logged.
        self.opener = opener or urllib.request.build_opener(_NoRedirect())
        self.clock = clock

    def __call__(self, route, day):
        if route not in ROUTES or type(day) is not date:
            raise ValueError('Invalid metadata request')
        url = ('https://site.api.espn.com/apis/site/v2/sports/' + route
               + '/scoreboard?' + urllib.parse.urlencode({'dates': day.strftime('%Y%m%d')}))
        request = urllib.request.Request(url, headers={
            'Accept': 'application/json', 'User-Agent': 'Project-Atlas-Sports-Metadata/1.0',
        })
        try:
            with self.opener.open(request, timeout=8) as response:
                if response.status != 200:
                    raise MetadataUnavailable('http', http_status=response.status)
                if response.headers.get_content_type() != 'application/json':
                    raise MetadataUnavailable('invalid-response')
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise MetadataUnavailable('response-budget')
            payload = json.loads(raw, object_pairs_hook=_unique)
            parse_scoreboard(route, payload)
            return payload
        except urllib.error.HTTPError as error:
            code = error.code
            wait = retry_after_seconds(error.headers.get('Retry-After'), self.clock()) if code == 429 else 15
            error.close()
            raise MetadataUnavailable('rate-limit' if code == 429 else 'http',
                                      retry_after=wait, http_status=code) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise MetadataUnavailable('network', retry_after=15) from None
        except (ValueError, UnicodeError, MetadataError):
            raise MetadataUnavailable('invalid-response', retry_after=15) from None


def _fetch_worker():
    """Fixed child entry point: no state access and only sanitized JSON on stdout."""
    request = json.loads(sys.stdin.buffer.read(4097))
    try:
        payload = ESPNDayTransport()(request['route'], date.fromisoformat(request['day']))
        result = {'outcome': 'success', 'payload': payload}
    except MetadataUnavailable as error:
        result = {'outcome': 'failure', 'category': error.category,
                  'retry_after': error.retry_after, 'http_status': error.http_status}
    sys.stdout.write(json.dumps(result, separators=(',', ':'), ensure_ascii=False, allow_nan=False))


class BoundedESPNTransport:
    """A separate short-lived fetch process gives DNS, TLS and reads one deadline.

    Only the parent owns persistent cache/budget state. subprocess.run kills and
    waits for the child on timeout; no fetch threads or orphan retries are left.
    """
    def __init__(self, *, deadline_seconds=8, runner=subprocess.run):
        if not math.isfinite(deadline_seconds) or not 0 < deadline_seconds <= 10:
            raise ValueError('Invalid provider deadline')
        self.deadline_seconds, self.runner = deadline_seconds, runner

    def __call__(self, route, day):
        if route not in ROUTES or type(day) is not date:
            raise ValueError('Invalid metadata request')
        environment = dict(os.environ)
        environment['PYTHONPATH'] = str(Path(__file__).resolve().parents[1])
        arguments = [sys.executable, '-B', '-c',
                     'from providers.metadata_broker import _fetch_worker; _fetch_worker()']
        try:
            response = self.runner(arguments,
                input=json.dumps({'route': route, 'day': day.isoformat()}).encode(),
                capture_output=True, timeout=self.deadline_seconds, env=environment)
        except subprocess.TimeoutExpired:
            raise MetadataUnavailable('deadline', retry_after=15) from None
        except OSError:
            raise MetadataUnavailable('fetch-process', retry_after=15) from None
        if response.returncode != 0 or len(response.stdout) > 4_100_000:
            raise MetadataUnavailable('fetch-process', retry_after=15)
        try:
            result = json.loads(response.stdout)
            if result['outcome'] == 'failure':
                category = result['category']
                if category not in {'http','rate-limit','network','invalid-response','response-budget'}:
                    raise ValueError('Invalid worker category')
                wait = result['retry_after']
                status = result['http_status']
                if type(wait) not in (int, float) or not math.isfinite(wait) or not 0 <= wait <= 3600:
                    raise ValueError('Invalid worker retry interval')
                if status is not None and (type(status) is not int or not 100 <= status <= 599):
                    raise ValueError('Invalid worker HTTP status')
                raise MetadataUnavailable(category, retry_after=wait, http_status=status)
            if result['outcome'] != 'success':
                raise ValueError('Invalid worker outcome')
            payload = result['payload']
            parse_scoreboard(route, payload)
            return payload
        except (KeyError, ValueError, TypeError):
            raise MetadataUnavailable('invalid-response', retry_after=15) from None


@dataclass(frozen=True)
class MetadataSnapshot:
    route: str
    requested_day: str
    events: tuple
    observed_at: float
    expires_at: float
    cache_hit: bool
    stale: bool = False

    @property
    def outcome(self):
        return 'events' if self.events else 'empty'


class MetadataBroker:
    def __init__(self, store, *, transport=None, clock=time.time,
                 hourly_budget=96, current_ttl=60, future_ttl=900):
        if type(hourly_budget) is not int or not 1 <= hourly_budget <= 1000:
            raise ValueError('Invalid metadata request budget')
        if any(type(v) is not int or not 1 <= v <= 3600 for v in (current_ttl, future_ttl)):
            raise ValueError('Invalid metadata cache lifetime')
        self.store, self.clock = store, clock
        self.transport = transport or BoundedESPNTransport()
        self.hourly_budget = hourly_budget
        self.current_ttl, self.future_ttl = current_ttl, future_ttl

    def _request(self, route, day):
        now = self.clock()
        if not math.isfinite(now) or now < 0:
            raise MetadataUnavailable('clock')
        if route not in ROUTES or type(day) is not date:
            raise ValueError('Invalid metadata request')
        today = datetime.fromtimestamp(now, timezone.utc).date()
        if not -1 <= (day - today).days <= 7:
            raise ValueError('Metadata request outside bounded horizon')
        return now, today, day.isoformat(), route + ':' + day.isoformat()

    def _snapshot(self, route, day, row, now, *, cache_hit, stale=False):
        payload, observed, expires = row
        if not all(type(v) in (int, float) and math.isfinite(v) for v in (observed, expires)) or observed > now or expires < observed:
            raise MetadataUnavailable('cache-clock')
        try:
            events = parse_scoreboard(route, json.loads(payload))
        except (ValueError, TypeError):
            raise MetadataUnavailable('cache-invalid') from None
        return MetadataSnapshot(route, day, events, observed, expires, cache_hit, stale)

    def fetch_day(self, route, day):
        # One process-shared lock intentionally bounds all provider concurrency to one.
        # The attempt/unknown-outcome reservation is committed BEFORE network access.
        with self.store.locked():
            now, today, key_day, key = self._request(route, day)
            with self.store.connection() as connection:
                row = connection.execute(
                    'SELECT payload, observed, expires FROM metadata_cache WHERE route=? AND day=?',
                    (route, key_day)).fetchone()
                if row and row[2] > now:
                    return self._snapshot(route, key_day, row, now, cache_hit=True)
                latest = connection.execute('SELECT MAX(stamp) FROM metadata_attempts').fetchone()[0]
                if latest is not None and latest > now:
                    raise MetadataUnavailable('clock-regressed')
                hold = connection.execute(
                    'SELECT MAX(until_stamp) FROM metadata_holds WHERE key IN (?, ?)',
                    (key, 'espn:cooldown')).fetchone()[0]
                if hold is not None and hold > now:
                    raise MetadataUnavailable('cooldown-or-unknown-outcome', retry_after=math.ceil(hold-now))
                connection.execute('DELETE FROM metadata_attempts WHERE stamp<=?', (now-3600,))
                count, oldest = connection.execute('SELECT COUNT(*),MIN(stamp) FROM metadata_attempts').fetchone()
                if count >= self.hourly_budget:
                    raise MetadataUnavailable('request-budget', retry_after=max(1, math.ceil(oldest+3600-now)))
                connection.execute('INSERT INTO metadata_attempts VALUES (?)', (now,))
                connection.execute('INSERT OR REPLACE INTO metadata_holds VALUES (?,?)', (key, now+30))
            try:
                payload = self.transport(route, day)
                parse_scoreboard(route, payload)
                encoded = json.dumps(payload, separators=(',', ':'), allow_nan=False)
                if len(encoded.encode()) > 4_000_000:
                    raise MetadataUnavailable('response-budget')
            except (MetadataUnavailable, ValueError, TypeError, OSError) as error:
                if not isinstance(error, MetadataUnavailable):
                    error = MetadataUnavailable('invalid-response' if isinstance(error, (ValueError, TypeError)) else 'network')
                wait = max(15, min(3600, error.retry_after))
                failure_at = self.clock()
                if not math.isfinite(failure_at) or failure_at < now:
                    failure_at = now
                with self.store.connection() as connection:
                    connection.execute('INSERT OR REPLACE INTO metadata_holds VALUES (?,?)', (key, failure_at+wait))
                    if error.http_status == 429:
                        connection.execute('INSERT OR REPLACE INTO metadata_holds VALUES (?,?)', ('espn:cooldown', failure_at+wait))
                raise error from None
            observed = self.clock()
            if not math.isfinite(observed) or observed < now:
                raise MetadataUnavailable('clock-regressed')
            expires = observed + (self.future_ttl if day > today else self.current_ttl)
            with self.store.connection() as connection:
                connection.execute('INSERT OR REPLACE INTO metadata_cache VALUES (?,?,?,?,?)',
                                   (route, key_day, encoded, observed, expires))
                connection.execute('DELETE FROM metadata_holds WHERE key=?', (key,))
                connection.execute('DELETE FROM metadata_cache WHERE expires<?', (observed-86400,))
            return self._snapshot(route, key_day, (encoded, observed, expires), observed, cache_hit=False)

    def peek_stale(self, route, day, *, max_age=3600):
        """Explicit last-known read; never calls upstream or claims fresh provider health."""
        if type(max_age) is not int or not 1 <= max_age <= 86400:
            raise ValueError('Invalid last-known age budget')
        now, _, key_day, _ = self._request(route, day)
        with self.store.locked(), self.store.connection() as connection:
            row = connection.execute(
                'SELECT payload, observed, expires FROM metadata_cache WHERE route=? AND day=?',
                (route, key_day)).fetchone()
            if not row or now-row[1] > max_age:
                return None
            return self._snapshot(route, key_day, row, now, cache_hit=True, stale=row[2] <= now)
