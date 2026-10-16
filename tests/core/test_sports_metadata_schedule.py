import copy
from datetime import date, datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'modules/sports/src'))
sys.path.insert(0,str(ROOT))
from providers.metadata_broker import MetadataBroker, MetadataUnavailable
from providers.metadata_store import MetadataStore
from providers.metadata_schedule import (
    collect_schedule, schedule_days, schedule_document, parse_schedule,
    refresh_one_schedule_day,
)
from providers.metadata_client import MetadataWriterClient
from providers.espn_metadata import LEAGUE_UIDS
import private_api

STAMP=datetime(2026,10,16,tzinfo=timezone.utc).timestamp()
ROUTE='football/nfl'
START='2026-10-18T00:00:00-04:00'
END='2026-10-19T00:00:00-04:00'


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.now=STAMP
        fixture=json.loads((ROOT/'tests/fixtures/sports/espn-metadata-20261016.json').read_text())
        self.nfl=next(row['payload'] for row in fixture['samples'] if row['route']==ROUTE)
        self.calls=[]
        self.failure=None
        def fetch(route,day):
            self.calls.append((route,day))
            if self.failure:
                raise self.failure
            return copy.deepcopy(self.nfl if day==date(2026,10,18) else self.empty(route))
        self.broker=MetadataBroker(MetadataStore(Path(self.tmp.name)/'state.sqlite'),
            transport=fetch,clock=lambda:self.now)

    def empty(self,route=ROUTE):
        return {'leagues':[{'uid':LEAGUE_UIDS[route]}],'events':[]}

    def collect(self,start=START,end=END):
        return collect_schedule(self.broker,ROUTE,start,end,now=self.now)

    def put(self,day,payload,observed=None,expires=None):
        observed=self.now if observed is None else observed
        expires=observed+60 if expires is None else expires
        with self.broker.store.locked(),self.broker.store.connection() as connection:
            connection.execute('INSERT OR REPLACE INTO metadata_cache VALUES (?,?,?,?,?)',
                (ROUTE,day,json.dumps(payload),observed,expires))

    def fill(self,payload=None):
        for day in ('2026-10-17','2026-10-18','2026-10-19'):
            self.put(day,(self.nfl if payload is None else payload) if day=='2026-10-18' else self.empty())

    def test_cold_cache_is_partial_and_does_not_fetch(self):
        result=self.collect()
        self.assertEqual(result.outcome,'partial')
        self.assertFalse(result.all_buckets_fresh)
        self.assertEqual([row.status for row in result.buckets],['missing']*3)
        self.assertEqual(result.events,())
        self.assertEqual(self.calls,[])

    def test_sunday_window_includes_all_twelve_captured_games_and_monday_utc(self):
        self.fill()
        result=self.collect()
        self.assertEqual(result.outcome,'events')
        self.assertEqual(len(result.events),12)
        sunday_night=next(row for row in result.events if row.event.provider_event_id=='401873007')
        self.assertEqual(sunday_night.event.start_at,'2026-10-19T00:20:00Z')
        self.assertEqual(len(result.upcoming(self.now)),12)
        self.assertEqual(self.calls,[])

    def test_checked_empty_is_different_from_unchecked(self):
        self.fill(self.empty())
        result=self.collect()
        self.assertTrue(result.all_buckets_fresh)
        self.assertEqual(result.outcome,'empty')
        self.assertEqual(self.calls,[])

    def test_missing_day_does_not_hide_other_observed_games(self):
        self.put('2026-10-18',self.nfl)
        result=self.collect()
        self.assertEqual(len(result.events),12)
        self.assertEqual(result.outcome,'partial')

    def test_stale_schedule_retains_age_but_cannot_prove_live(self):
        payload=copy.deepcopy(self.nfl)
        for event in payload['events']:
            event['status']={'type':{'name':'STATUS_IN_PROGRESS','state':'in','completed':False}}
        self.fill(payload)
        self.now+=61
        result=self.collect()
        self.assertEqual(len(result.events),12)
        self.assertTrue(all(row.stale for row in result.events))
        self.assertEqual(result.outcome,'partial')
        self.assertEqual(result.fresh_live(datetime(2026,10,19,tzinfo=timezone.utc).timestamp()),())

    def test_newer_reschedule_outside_window_removes_old_occurrence(self):
        self.fill()
        moved=copy.deepcopy(self.nfl)
        moved['events'][0]['competitions'][0]['date']='2026-10-20T13:30Z'
        self.now+=1
        self.put('2026-10-19',moved)
        result=self.collect()
        self.assertNotIn(self.nfl['events'][0]['id'],{row.event.provider_event_id for row in result.events})
        self.assertEqual(len(result.events),11)

    def test_newer_cancelled_record_replaces_old_scheduled_record(self):
        self.fill()
        cancelled=copy.deepcopy(self.nfl)
        cancelled['events'][0]['status']={'type':{'name':'STATUS_CANCELED','state':'pre','completed':False}}
        self.now+=1
        self.put('2026-10-19',cancelled)
        result=self.collect()
        self.assertEqual(len(result.events),12)
        self.assertEqual(len(result.upcoming(self.now)),11)
        self.assertEqual(result.conflicting_event_ids,())

    def test_equal_observation_conflict_is_not_resolved_by_bucket_order(self):
        self.fill()
        conflict=copy.deepcopy(self.nfl)
        conflict['events'][0]['name']='Conflicting title'
        self.put('2026-10-19',conflict)
        result=self.collect()
        self.assertEqual(result.conflicting_event_ids,(self.nfl['events'][0]['id'],))
        self.assertEqual(len(result.events),11)
        self.assertEqual(result.outcome,'partial')

    def test_identical_overlapping_buckets_collapse_by_route_and_event(self):
        self.fill()
        self.put('2026-10-19',self.nfl)
        result=self.collect()
        self.assertEqual(len(result.events),12)
        self.assertEqual(result.conflicting_event_ids,())

    def test_unverified_time_does_not_turn_into_empty_success(self):
        payload=copy.deepcopy(self.nfl)
        payload['events']=payload['events'][:1]
        payload['events'][0]['competitions'][0]['timeValid']=False
        self.fill(payload)
        result=self.collect()
        self.assertEqual(result.events,())
        self.assertEqual(result.unknown_time_event_ids,(payload['events'][0]['id'],))
        self.assertEqual(result.outcome,'partial')

    def test_invalid_cached_bucket_is_explicit(self):
        self.fill()
        self.put('2026-10-18',{})
        result=self.collect()
        self.assertEqual([row.status for row in result.buckets],['fresh','invalid','fresh'])
        self.assertEqual(result.outcome,'partial')
        self.assertEqual(self.calls,[])

    def test_future_observation_cannot_be_fresh(self):
        self.fill()
        self.put('2026-10-18',self.nfl,observed=self.now+10)
        self.assertEqual(self.collect().buckets[1].status,'invalid')

    def test_ufc_stays_one_card_with_thirteen_bouts(self):
        from providers.metadata_broker import MetadataDayCache, MetadataSnapshot
        from providers.espn_metadata import parse_scoreboard
        from providers.metadata_schedule import reconcile_schedule
        fixture=json.loads((ROOT/'tests/fixtures/sports/espn-metadata-20261016.json').read_text())
        row=next(row for row in fixture['samples'] if row['route']=='mma/ufc')
        events=parse_scoreboard('mma/ufc',row['payload'])
        start='2026-10-16T00:00:00Z';end='2026-10-23T00:00:00Z'
        days=schedule_days('mma/ufc',start,end,self.now)[2]
        buckets=tuple(MetadataDayCache(day.isoformat(),
            MetadataSnapshot('mma/ufc',day.isoformat(),events if day==date(2026,10,17) else (),
                             self.now,self.now+60,True),'fresh',0) for day in days)
        result=reconcile_schedule('mma/ufc',start,end,self.now,buckets)
        self.assertEqual(len(result.events),1)
        self.assertEqual(result.events[0].event.kind,'fight_card')
        self.assertEqual(len(result.events[0].event.competitions),13)

    def test_half_open_window_excludes_exact_end(self):
        self.fill()
        end=self.nfl['events'][0]['competitions'][0]['date']
        result=self.collect(start=START,end=end)
        self.assertEqual(result.events,())

    def test_rolling_seven_days_has_bounded_nine_bucket_union(self):
        start=datetime.fromtimestamp(self.now,timezone.utc)
        result=self.collect(start=start.isoformat(),end=(start+timedelta(days=7)).isoformat())
        self.assertEqual(len(result.buckets),9)
        self.assertEqual(self.calls,[])

    def test_invalid_naive_long_or_old_window_does_not_touch_cache(self):
        for start,end in (('2026-10-18T00:00:00',END),(END,START),
                          (START,'2026-10-30T00:00:00Z'),('2020-01-01T00:00:00Z',END)):
            with self.subTest(start=start,end=end),patch.object(self.broker,'read_days') as reader,self.assertRaises(ValueError):
                self.collect(start,end)
            reader.assert_not_called()

    def test_duplicate_day_selection_rejected(self):
        with self.assertRaises(ValueError):
            self.broker.read_days(ROUTE,[date(2026,10,18)]*2)

    def test_missing_buckets_preserve_cooldown_without_fetching(self):
        with self.broker.store.connection() as connection:
            connection.execute('INSERT INTO metadata_holds VALUES (?,?)',('espn:cooldown',self.now+120))
        result=self.collect()
        self.assertEqual({row.retry_after_seconds for row in result.buckets},{120})
        self.assertIsNone(refresh_one_schedule_day(self.broker,ROUTE,START,END,now=self.now))
        self.assertEqual(self.calls,[])

    def test_explicit_refresher_attempts_at_most_one_bucket_per_call(self):
        result=refresh_one_schedule_day(self.broker,ROUTE,START,END,now=self.now)
        self.assertIsNotNone(result)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(sum(row.status=='fresh' for row in self.collect().buckets),1)
        for _ in range(2):
            refresh_one_schedule_day(self.broker,ROUTE,START,END,now=self.now)
        self.assertEqual(len(self.calls),3)
        self.assertEqual(len(self.collect().events),12)
        self.assertIsNone(refresh_one_schedule_day(self.broker,ROUTE,START,END,now=self.now))
        self.assertEqual(len(self.calls),3)

    def test_refresh_failure_does_not_claim_bucket_success(self):
        self.failure=MetadataUnavailable('network',retry_after=30)
        with self.assertRaises(MetadataUnavailable):
            refresh_one_schedule_day(self.broker,ROUTE,START,END,now=self.now)
        result=self.collect()
        self.assertEqual(result.outcome,'partial')
        self.assertEqual(len(self.calls),1)
        self.assertEqual(sum(row.retry_after_seconds>0 for row in result.buckets),1)

    def test_wire_roundtrip_preserves_stale_partial_and_rejects_false_freshness(self):
        self.fill()
        self.now+=61
        original=self.collect()
        document=json.loads(json.dumps(schedule_document(original)))
        result=parse_schedule(document,route=ROUTE,start_at=START,end_at=END)
        self.assertEqual(result,original)
        document['buckets'][1]['status']='fresh'
        with self.assertRaises(ValueError):
            parse_schedule(document,route=ROUTE,start_at=START,end_at=END)

    def test_delivery_rechecks_expiry_without_renewing_observation(self):
        from providers.metadata_schedule import reevaluate_schedule
        self.fill()
        original=self.collect()
        result=reevaluate_schedule(original,self.now+61)
        self.assertEqual(result.outcome,'partial')
        self.assertTrue(all(row.stale for row in result.events))
        self.assertEqual({row.observed_at for row in result.events},{STAMP})

    def test_schedule_response_budget_fails_instead_of_truncating(self):
        self.fill()
        with patch('providers.metadata_service.snapshot_document',return_value={'oversize':'x'*1_400_000}):
            with self.assertRaises(MetadataUnavailable) as caught:
                schedule_document(self.collect())
        self.assertEqual(caught.exception.category,'schedule-response-budget')

    def test_wrong_window_or_missing_wire_bucket_rejected(self):
        document=schedule_document(self.collect())
        for change in ({'buckets':document['buckets'][:-1]}, {'end_at':'2026-10-20T04:00:00Z'}, {'extra':'value'}):
            with self.subTest(change=change),self.assertRaises(ValueError):
                parse_schedule(dict(document,**change),route=ROUTE,start_at=START,end_at=END)

    def test_http_cache_only_schedule_roundtrip_with_authentication(self):
        self.fill()
        with patch.dict(os.environ,{'ATLAS_SPORTS_WRITER_TOKEN':'test-only',
                                    'ATLAS_SPORTS_METADATA_STATE_DIR':self.tmp.name}),\
             patch('providers.metadata_service._configured_broker',return_value=self.broker),\
             patch('providers.metadata_service.metadata_now',return_value=self.now):
            server=ThreadingHTTPServer(('127.0.0.1',0),private_api.Handler)
            thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.01),daemon=True)
            thread.start()
            try:
                client=MetadataWriterClient('http://127.0.0.1:'+str(server.server_port),'test-only',clock=lambda:self.now)
                result=client.fetch_schedule(ROUTE,START,END)
                self.assertEqual(len(result.events),12)
                self.assertEqual(self.calls,[])
                bad=MetadataWriterClient(client.base_url,'incorrect',clock=lambda:self.now)
                with self.assertRaises(MetadataUnavailable) as caught:
                    bad.fetch_schedule(ROUTE,START,END)
                self.assertEqual(caught.exception.http_status,401)
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
