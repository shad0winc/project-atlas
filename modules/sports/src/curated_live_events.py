"""Opt-in cache-to-live projection. No public sports-provider fetch surface."""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
import os
import time
import urllib.parse
import urllib.request

from subscriptions import active_subscriptions, game_matches_subscription

ROUTES = {'nfl':'football/nfl', 'nba':'basketball/nba', 'mlb':'baseball/mlb',
          'nhl':'hockey/nhl', 'premier-league':'soccer/eng.1'}

class CuratedLiveUnavailable(RuntimeError):
    pass

def require(value):
    if not value:
        raise CuratedLiveUnavailable('Curated live cache could not be validated.')

def stamp(value):
    require(isinstance(value,str) and len(value)<=64)
    try:
        result=datetime.fromisoformat(value.replace('Z','+00:00'))
    except ValueError:
        raise CuratedLiveUnavailable('Curated live timestamp is invalid.') from None
    require(result.tzinfo is not None)
    return result.astimezone(timezone.utc)

def text(value):
    require(isinstance(value,str) and 0<len(value.strip())<=256
            and not any(ord(char)<32 for char in value))
    return value.strip()

def public_id(value,route):
    value=text(value)
    require(value.startswith(route.replace('/','-')+'-'))
    return value

def project_events(schedule,directory,subscriptions,*,route,now,pregame_minutes=60):
    """Keep exact ESPN identities and fresh provider statuses; never infer live."""
    require(schedule.get('provider')==directory.get('provider')=='espn'
            and schedule.get('provider_league_id')==directory.get('provider_league_id')==route
            and schedule.get('status') in ('ready','partial') and directory.get('status')=='ready')
    require(isinstance(directory.get('teams'),list) and len(directory['teams'])<=1000
            and isinstance(schedule.get('events'),list) and len(schedule['events'])<=500)
    require(stamp(directory['observed_at'])<=now<stamp(directory['expires_at']))
    teams={}
    for row in directory['teams']:
        identity=public_id(row.get('id'),route)
        require(identity not in teams);teams[identity]=text(row.get('name'))
    events={}
    for row in schedule['events']:
        require(isinstance(row,dict) and row.get('provider')=='espn'
                and row.get('provider_league_id')==route)
        identity=public_id(row.get('provider_event_id'),route)
        require(identity not in events)
        # Remember even excluded identities so duplicates cannot select a preferred status.
        events[identity]=None
        if row.get('status') not in ('scheduled','live'):
            continue
        observed=stamp(row.get('metadata_observed_at'));expires=stamp(row.get('metadata_expires_at'))
        if not observed<=now<expires or now-observed>timedelta(minutes=5):
            continue
        start=stamp(row.get('start_at'))
        if not now-timedelta(hours=6)<=start<=now+timedelta(minutes=pregame_minutes):
            continue
        home=public_id(row.get('home_team_id'),route);away=public_id(row.get('away_team_id'),route)
        require(home!=away and home in teams and away in teams)
        game={key:row[key] for key in ('provider','provider_event_id','provider_league_id',
            'home_team_id','away_team_id','start_at','status','metadata_observed_at','metadata_expires_at')}
        game.update(id='espn-'+identity,name=text(row.get('name')),sport=text(row.get('sport')),
            league=text(row.get('league')),home_team=teams[home],away_team=teams[away],
            lifecycle_state=row['status'],record=False)
        if any(game_matches_subscription(game,subscription) for subscription in subscriptions):
            events[identity]=game
    result=[game for game in events.values() if game is not None]
    require(len(result)<=64)
    return sorted(result,key=lambda game:(game['start_at'],game['provider_event_id']))

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise CuratedLiveUnavailable('Curated writer redirects are refused.')

class CacheClient:
    def __init__(self,base_url,token,*,opener=None,clock=time.monotonic):
        parsed=urllib.parse.urlsplit(base_url)
        require(parsed.scheme in ('http','https') and parsed.hostname
            and not parsed.username and not parsed.password and parsed.path in ('','/')
            and not parsed.query and not parsed.fragment and bool(token))
        if parsed.hostname not in ('atlas-sports-writer','localhost'):
            try:
                require(ipaddress.ip_address(parsed.hostname).is_private)
            except ValueError:
                raise CuratedLiveUnavailable('Curated writer origin must be internal.') from None
        self.base_url=base_url.rstrip('/');self.token=token;self.clock=clock
        self.deadline=clock()+20;self.calls=0
        self.opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect()).open

    def get(self,kind,query):
        require(kind in ('teams','schedule') and self.calls<10 and self.clock()<self.deadline)
        self.calls+=1
        url=self.base_url+'/internal/v1/curated/'+kind+'?'+urllib.parse.urlencode(query)
        request=urllib.request.Request(url,headers={'Authorization':'Bearer '+self.token,'Accept':'application/json'},method='GET')
        try:
            with self.opener(request,timeout=min(3,max(.1,self.deadline-self.clock()))) as response:
                require(response.status==200)
                raw=response.read(4*1024**2+1);require(len(raw)<=4*1024**2)
            def unique(pairs):
                result={}
                for key,value in pairs:
                    require(key not in result);result[key]=value
                return result
            result=json.loads(raw,object_pairs_hook=unique)
            require(isinstance(result,dict));return result
        except CuratedLiveUnavailable:
            raise
        except Exception:
            raise CuratedLiveUnavailable('Curated writer cache read failed.') from None

def load_curated_live_events(*,subscriptions=None,now=None,pregame_minutes=60,client=None,environ=None):
    env=os.environ if environ is None else environ
    enabled=env.get('ATLAS_SPORTS_CURATED_LIVE_ENABLED','0')
    require(enabled in ('0','1'))
    if enabled=='0':
        return []
    require(type(pregame_minutes) is int and 0<=pregame_minutes<=180)
    subscriptions=active_subscriptions() if subscriptions is None else subscriptions
    subscriptions=[row for row in subscriptions if row.get('provider')=='espn' and row.get('enabled',True)]
    if not subscriptions:
        return []
    now=now or datetime.now(timezone.utc);require(now.tzinfo is not None)
    demanded=[]
    for competition,route in ROUTES.items():
        # Only a matching league/event/team subscription can demand this route.
        if not any((row.get('type')=='league' and row.get('id')==route)
            or (row.get('type') in ('event','team') and str(row.get('id','')).startswith(route.replace('/','-')+'-'))
            for row in subscriptions):
            continue
        demanded.append((competition,route))
    if not demanded:
        return []
    client=client or CacheClient(env.get('ATLAS_SPORTS_WRITER_URL','http://atlas-sports-writer:8003'),
                                env.get('ATLAS_SPORTS_WRITER_TOKEN',''))
    result=[]
    for competition,route in demanded:
        directory=client.get('teams',{'competition':competition})
        schedule=client.get('schedule',dict(competition=competition,
            start_at=(now-timedelta(hours=6)).isoformat(),
            end_at=(now+timedelta(minutes=pregame_minutes,seconds=1)).isoformat()))
        result.extend(project_events(schedule,directory,subscriptions,route=route,now=now,pregame_minutes=pregame_minutes))
    require(len(result)<=64)
    return result

def merge_event_games(legacy,curated):
    result=list(legacy);seen={(row.get('provider'),row.get('provider_event_id')) for row in result}
    for row in curated:
        key=(row['provider'],row['provider_event_id'])
        require(key not in seen);seen.add(key);result.append(row)
    return result

class ImportedStreamSnapshot:
    """Reuse one imported stream inventory per account in one controller cycle."""
    def __init__(self,client):
        self.client=client;self.streams={}
    def list_streams(self,*,account_id):
        if account_id not in self.streams:
            require(len(self.streams)<32)
            self.streams[account_id]=tuple(self.client.list_streams(account_id=account_id))
        return self.streams[account_id]
    def __getattr__(self,name):
        return getattr(self.client,name)
