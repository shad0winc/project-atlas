"""Private writer client for API/background metadata consumers; no upstream access."""
from datetime import date
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request

from providers.espn_metadata import ROUTES
from providers.metadata_broker import MetadataUnavailable, _NoRedirect, _unique
from providers.metadata_service import parse_snapshot


class MetadataWriterClient:
    def __init__(self, base_url, token, *, timeout=22, opener=None, clock=time.time):
        parsed = urllib.parse.urlsplit(base_url)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {'', '/'}):
            raise ValueError('Invalid private metadata writer address')
        if not isinstance(token, str) or not token.strip() or any(c in token for c in '\r\n'):
            raise ValueError('Private metadata writer credential is required')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError('Invalid private metadata timeout')
        self.base_url, self.token, self.timeout = base_url.rstrip('/'), token.strip(), timeout
        self.clock = clock
        self.opener = opener or urllib.request.build_opener(_NoRedirect())

    def fetch_day(self, route, day):
        if route not in ROUTES or type(day) is not date:
            raise ValueError('Invalid metadata request')
        return self._fetch('day', route, day)

    def fetch_teams(self, route):
        if route not in ROUTES or ROUTES[route][2]:
            raise ValueError('Invalid team directory request')
        return self._fetch('teams', route)

    def fetch_schedule(self, route, start_at, end_at):
        from providers.metadata_schedule import schedule_days, parse_schedule, reevaluate_schedule
        schedule_days(route, start_at, end_at, self.clock())
        document = self._request_document('schedule', {
            'route': route, 'start_at': start_at, 'end_at': end_at,
        })
        try:
            schedule = parse_schedule(document, route=route, start_at=start_at, end_at=end_at)
            now = self.clock()
            if not math.isfinite(now) or not 0 <= now-schedule.evaluated_at <= 30:
                raise MetadataUnavailable('writer-snapshot-age')
            return reevaluate_schedule(schedule, now)
        except (ValueError, TypeError, KeyError):
            raise MetadataUnavailable('writer-response') from None

    def _fetch(self, kind, route, day=None):
        query = {'route': route}
        if day is not None:
            query['day'] = day.isoformat()
        document = self._request_document(kind, query)
        try:
            snapshot = parse_snapshot(document, kind=kind, route=route, day=day)
            now = self.clock()
            if not math.isfinite(now) or not snapshot.observed_at <= now < snapshot.expires_at:
                raise MetadataUnavailable('writer-snapshot-age')
            return snapshot
        except (ValueError, TypeError, KeyError):
            raise MetadataUnavailable('writer-response') from None

    def _request_document(self, kind, query):
        request = urllib.request.Request(
            self.base_url + '/internal/v1/metadata/' + kind + '?' + urllib.parse.urlencode(query),
            headers={'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'},
        )
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                if response.status != 200 or response.headers.get_content_type() != 'application/json':
                    raise MetadataUnavailable('writer-response')
                raw = response.read(4_000_001)
            if len(raw) > 4_000_000:
                raise MetadataUnavailable('writer-response-budget')
            return json.loads(raw, object_pairs_hook=_unique)
        except urllib.error.HTTPError as error:
            status = error.code
            error.close()
            raise MetadataUnavailable('writer-unavailable', http_status=status) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise MetadataUnavailable('writer-network') from None
        except (ValueError, TypeError, KeyError):
            raise MetadataUnavailable('writer-response') from None
