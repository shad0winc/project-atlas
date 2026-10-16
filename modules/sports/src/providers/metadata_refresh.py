"""Explicitly enabled writer-owned refresh, using the existing shared broker.

No worker, state or configuration is created by importing this module.
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time

from providers.espn_metadata import ROUTES
from providers.metadata_broker import MetadataUnavailable, _unique


class RefreshPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class RefreshPolicy:
    routes: tuple[str, ...]
    hourly_budget: int
    current_ttl: int
    past_ttl: int
    future_ttl: int
    directory_ttl: int
    tick_seconds: int
    generation: str

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @property
    def broker_settings(self):
        return tuple(sorted((key,value) for key,value in asdict(self).items()
                            if key not in {'routes','tick_seconds','generation'}))


def parse_refresh_policy(data):
    if not isinstance(data,dict) or type(data.get('version')) is not int or data['version']!=1 or type(data.get('enabled')) is not bool:
        raise RefreshPolicyError('Invalid metadata refresh policy')
    if not data['enabled']:
        if set(data)!={'version','enabled'}:
            raise RefreshPolicyError('Invalid disabled refresh policy')
        return None
    if set(data)!={'version','enabled',*RefreshPolicy.__dataclass_fields__}:
        raise RefreshPolicyError('Invalid metadata refresh policy fields')
    routes=data['routes']
    if not isinstance(routes,list) or not 1<=len(routes)<=len(ROUTES) or any(not isinstance(route,str) or route not in ROUTES for route in routes) or len(set(routes))!=len(routes):
        raise RefreshPolicyError('Invalid refresh routes')
    bounds={'hourly_budget':(1,1000),'current_ttl':(30,3600),'past_ttl':(900,3600),
            'future_ttl':(900,3600),'directory_ttl':(3600,3600),'tick_seconds':(1,30)}
    for key,(low,high) in bounds.items():
        if type(data[key]) is not int or not low<=data[key]<=high:
            raise RefreshPolicyError('Invalid refresh limits')
    if not isinstance(data['generation'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',data['generation']):
        raise RefreshPolicyError('Invalid refresh generation')
    # This is an Atlas planning limit, not an ESPN quota or a freshness SLA.
    nominal=len(routes)*(math.ceil(3600/data['current_ttl'])+
        math.ceil(3600/data['past_ttl'])+7*math.ceil(3600/data['future_ttl']))
    nominal+=sum(not ROUTES[route][2] for route in routes)*math.ceil(3600/data['directory_ttl'])
    if nominal>data['hourly_budget']:
        raise RefreshPolicyError('Refresh cadence exceeds the configured nominal request budget')
    return RefreshPolicy(tuple(routes),**{key:data[key] for key in RefreshPolicy.__dataclass_fields__ if key!='routes'})


def load_refresh_policy(path=None):
    configured=os.environ.get('ATLAS_SPORTS_METADATA_REFRESH_FILE','') if path is None else str(path)
    if not configured:
        return None
    policy=Path(configured)
    if not policy.is_absolute():
        raise RefreshPolicyError('Refresh policy path must be absolute')
    try:
        descriptor=os.open(policy,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    except FileNotFoundError:
        return None
    except OSError:
        raise RefreshPolicyError('Refresh policy is unavailable') from None
    try:
        with os.fdopen(descriptor,'rb') as handle:
            info=os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid not in {0,os.geteuid()} or info.st_mode&0o022 or info.st_size>16384:
                raise RefreshPolicyError('Unsafe refresh policy file')
            raw=handle.read(16385)
        if len(raw)>16384:
            raise RefreshPolicyError('Refresh policy exceeds budget')
        return parse_refresh_policy(json.loads(raw,object_pairs_hook=_unique))
    except (ValueError,TypeError,KeyError,UnicodeError,OSError):
        raise RefreshPolicyError('Metadata refresh policy is invalid or unavailable') from None


@dataclass(frozen=True)
class RefreshJob:
    route: str
    day: object  # date for a scoreboard; None for its team directory
    priority: tuple


def next_refresh_job(broker,policy,now,*,stop_requested=lambda:False):
    today=datetime.fromtimestamp(now,timezone.utc).date()
    days=tuple(today+timedelta(days=offset) for offset in range(-1,8))
    jobs=[]
    for route in policy.routes:
        if stop_requested():return None
        _,buckets=broker.read_days(route,days)
        if stop_requested():return None
        for bucket in buckets:
            if bucket.status=='fresh' or bucket.retry_after_seconds:
                continue
            day=datetime.fromisoformat(bucket.requested_day).date()
            priority=(0 if day==today else 2 if bucket.snapshot is None else 3,
                      bucket.snapshot.expires_at if bucket.snapshot else -1,route,day.isoformat())
            jobs.append(RefreshJob(route,day,priority))
        if not ROUTES[route][2]:
            _,directory=broker.read_teams(route)
            if directory.status!='fresh' and directory.retry_after_seconds==0:
                priority=(1 if directory.snapshot is None else 3,
                          directory.snapshot.expires_at if directory.snapshot else -1,route,'@teams')
                jobs.append(RefreshJob(route,None,priority))
    return min(jobs,key=lambda job:job.priority) if jobs else None


class MetadataRefreshWorker:
    def __init__(self,policy_loader,broker_factory,*,clock=time.time):
        self.policy_loader,self.broker_factory,self.clock=policy_loader,broker_factory,clock
        self.stop_event=threading.Event()
        self.thread=None
        self.lock=threading.Lock()
        self._status={'version':1,'state':'starting','running':False,
                      'policy_fingerprint':None,'last_tick_at':None,
                      'last_provider_success_at':None,'last_failure_at':None,
                      'last_failure_category':None}

    def status(self):
        with self.lock:return dict(self._status)

    def update(self,**values):
        with self.lock:self._status.update(values)

    def tick(self):
        if self.stop_event.is_set():return 30
        now=self.clock()
        if not math.isfinite(now) or now<0:
            raise MetadataUnavailable('clock')
        policy=self.policy_loader()
        if policy is None:
            self.update(state='disabled',last_tick_at=now,policy_fingerprint=None)
            return 30
        self.update(policy_fingerprint=policy.fingerprint,last_tick_at=now)
        broker=self.broker_factory(policy)
        job=next_refresh_job(broker,policy,now,stop_requested=self.stop_event.is_set)
        if self.stop_event.is_set():return 30
        if job is None:
            self.update(state='waiting')
            return min(30,policy.tick_seconds)
        result=broker.fetch_day(job.route,job.day) if job.day is not None else broker.fetch_teams(job.route)
        if not result.cache_hit:
            self.update(state='observed',last_provider_success_at=result.observed_at,
                        last_failure_category=None)
        else:
            self.update(state='cache-hit')
        return policy.tick_seconds

    def failed(self,category,*,state='unavailable'):
        stamp=self.clock()
        if type(stamp) not in (int,float) or not math.isfinite(stamp) or stamp<0:
            stamp=None
        self.update(state=state,last_failure_at=stamp,last_failure_category=category)

    def _run(self):
        self.update(running=True)
        try:
            while not self.stop_event.is_set():
                try:
                    delay=self.tick()
                except RefreshPolicyError:
                    self.failed('configuration',state='configuration-error')
                    delay=30
                except MetadataUnavailable as error:
                    categories={'http','rate-limit','network','invalid-response','response-budget',
                        'deadline','fetch-process','request-budget','cooldown-or-unknown-outcome',
                        'clock','clock-regressed','cache-clock','cache-invalid'}
                    category=error.category if error.category in categories else 'unavailable'
                    self.failed(category)
                    delay=max(15,min(3600,error.retry_after))
                except Exception:
                    self.failed('internal')
                    delay=30
                self.stop_event.wait(delay)
        finally:
            self.update(running=False,state='stopped')

    def start(self):
        if self.thread is not None:
            raise RuntimeError('Metadata refresh worker was already started')
        self.thread=threading.Thread(target=self._run,name='atlas-metadata-refresh',daemon=True)
        self.thread.start()
        return self

    def close(self,timeout=25):
        self.stop_event.set()
        if self.thread is not None:self.thread.join(timeout)
        return self.thread is None or not self.thread.is_alive()


def start_configured_refresh():
    # Missing/disabled configuration starts no thread and opens no state.
    policy=load_refresh_policy()
    if policy is None:
        return None
    from providers.metadata_service import configured_broker
    configured_broker(policy)  # Validate explicit state/configuration before serving.
    return MetadataRefreshWorker(load_refresh_policy,lambda policy:configured_broker(policy)).start()
