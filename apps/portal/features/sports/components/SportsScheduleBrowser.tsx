"use client";

import { useEffect, useRef, useState } from "react";
import type { SportsEvent, SportsFollow } from "../types/sports";
import { matchesSportsFollow } from "../services/currentlyLive";
import { loadSportsLiveAvailability } from "../services/sports";
import { startLiveAvailabilityRefresh, type LiveAvailabilitySnapshot } from "../services/liveAvailabilityRefresh";
import { curatedEventFresh, curatedStartLabel, mergeSportsObservations } from "../services/curatedLiveState";
import {
  filterCuratedTeam, loadCuratedCatalog, loadCuratedSchedule, loadCuratedTeams,
  retainCuratedSchedule, type CuratedCatalog, type CuratedPeriod,
  type CuratedSchedule, type CuratedTeams,
} from "../services/curatedSchedule";

const PREGAME_WINDOW_MS = 60 * 60 * 1000;
const MAX_EVENT_AGE_MS = 6 * PREGAME_WINDOW_MS;

function inPlaybackWindow(event: SportsEvent, now: number): boolean {
  const start = Date.parse(event.startAt);
  return event.provider === "espn" &&
    (event.status === "scheduled" || event.status === "live") &&
    start >= now - MAX_EVENT_AGE_MS && start <= now + PREGAME_WINDOW_MS;
}

type Props = Readonly<{
  follows: readonly SportsFollow[];
  onScheduleChanged: (events: readonly SportsEvent[]) => void;
  onRequestEvent: (input: Readonly<{ provider: string; providerEventId: string }>) => Promise<unknown>;
  onWatchLive: (channelId: string) => Promise<void>;
  onCatalogAvailabilityChanged?: (enabled: boolean | null) => void;
  onFollow: (type: "team" | "league", id: string, provider: string) => Promise<void>;
}>;

export function SportsScheduleBrowser({ follows, onFollow, onCatalogAvailabilityChanged, onScheduleChanged, onRequestEvent, onWatchLive }: Props): React.ReactElement | null {
  const [catalog, setCatalog] = useState<CuratedCatalog | null>(null);
  const [competitionId, setCompetitionId] = useState("");
  const [period, setPeriod] = useState<CuratedPeriod>("today");
  const [teamId, setTeamId] = useState("");
  const [directory, setDirectory] = useState<CuratedTeams | null>(null);
  const [result, setResult] = useState<Readonly<{ key: string; snapshot: CuratedSchedule }> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [following, setFollowing] = useState(false);
  const [pendingEvent, setPendingEvent] = useState<string | null>(null);
  const [availability, setAvailability] = useState<LiveAvailabilitySnapshot>({});
  const [playbackMessage, setPlaybackMessage] = useState<{
    eventId: string;
    message: string;
  } | null>(null);
  const [refresh, setRefresh] = useState(0);
  const nextRefresh = useRef(0);
  const [refreshAt, setRefreshAt] = useState(0);
  const [now, setNow] = useState(Date.now);
  const key = `${competitionId}:${period}`;
  const competition = catalog?.competitions.find(item => item.id === competitionId);
  const snapshot = result?.key === key ? result.snapshot : null;
  const teams = directory?.competitionId === competitionId ? directory : null;
  const events = filterCuratedTeam(snapshot, teamId);

  const followedCompetitionsKey = JSON.stringify((catalog?.enabled ? catalog.competitions : [])
    .filter(({ status, providerLeagueId }) => {
      if (status !== "configured" || !providerLeagueId) return false;
      const prefix = providerLeagueId.replace("/", "-") + "-";
      return follows.some(follow => follow.enabled && follow.provider === "espn" &&
        (follow.type === "league" ? follow.providerId === providerLeagueId :
          (follow.type === "team" || follow.type === "event") && follow.providerId.startsWith(prefix)));
    }).map(({ id }) => id).sort());

  const playbackEventIds = JSON.stringify(events
    .filter(event => inPlaybackWindow(event, now) && follows.some(follow => matchesSportsFollow(event, follow)))
    .map(event => event.providerEventId).sort());

  useEffect(() => {
    const ids: string[] = JSON.parse(playbackEventIds);
    return startLiveAvailabilityRefresh({
      follows: ids.map(id => ({
        subscriptionId: id, type: "event", provider: "espn", providerId: id,
        name: "", userId: "", enabled: true, record: false, createdAt: null,
      })),
      load: (...args) => loadSportsLiveAvailability(...args),
      publish: setAvailability,
    });
  }, [playbackEventIds]);

  useEffect(() => {
    const controller = new AbortController();
    void loadCuratedCatalog(controller.signal).then(value => {
      if (controller.signal.aborted) return;
      setCatalog(value);
      onCatalogAvailabilityChanged?.(value.enabled);
      setCompetitionId(value.competitions.find(item => item.status === "configured")?.id ?? value.competitions[0]?.id ?? "");
    }).catch(() => {
      if (!controller.signal.aborted) onCatalogAvailabilityChanged?.(null);
    });
    return () => controller.abort();
  }, [onCatalogAvailabilityChanged]);

  useEffect(() => {
    if (!competition || competition.status !== "configured" || !competition.teamDirectorySupported) return;
    const controller = new AbortController();
    void loadCuratedTeams(competition.id, controller.signal).then(value => {
      if (!controller.signal.aborted) setDirectory(value);
    }).catch(() => { /* A missing team directory must not hide a cached league schedule. */ });
    return () => controller.abort();
  }, [competition]);

  useEffect(() => {
    if (!competition || competition.status !== "configured") return;
    const controller = new AbortController();
    // One cache read per selection. Background provider refresh is owned by the server.
    void (async () => {
      setBusy(true); setError(null);
      try {
        const value = await loadCuratedSchedule(competition.id, period, controller.signal);
        if (controller.signal.aborted) return;
        setResult(previous => ({ key, snapshot: retainCuratedSchedule(previous?.key === key ? previous.snapshot : null, value) }));
        nextRefresh.current = Date.now() + Math.max(60, value.retryAfterSeconds) * 1000;
      } catch {
        if (controller.signal.aborted) return;
        setError("Schedule refresh is unavailable. Previously loaded events remain visible; their times may have changed.");
        nextRefresh.current = Date.now() + 60_000;
      } finally {
        if (!controller.signal.aborted) {
          setBusy(false); setRefreshAt(nextRefresh.current); setNow(Date.now());
        }
      }
    })();
    return () => controller.abort();
  }, [competition, period, key, refresh]);

  useEffect(() => {
    const deadlines = [refreshAt, snapshot?.expiresAt ? Date.parse(snapshot.expiresAt) : 0].filter(value => value > now);
    if (!deadlines.length) return;
    const timer = setTimeout(() => setNow(Date.now()), Math.max(1, Math.min(...deadlines) - Date.now()));
    return () => clearTimeout(timer);
  }, [refreshAt, snapshot?.expiresAt, now]);

  useEffect(() => {
    const ids: string[] = JSON.parse(followedCompetitionsKey);
    const snapshots = new Map<string, CuratedSchedule>();
    let controller: AbortController | undefined;
    const refresh = async () => {
      if (document.visibilityState === "hidden" || controller) return;
      const current = new AbortController();
      controller = current;
      await Promise.all(ids.map(async id => {
        try {
          const next = await loadCuratedSchedule(id, "today", current.signal);
          if (!current.signal.aborted) snapshots.set(id, retainCuratedSchedule(snapshots.get(id) ?? null, next));
        } catch { /* Keep prior metadata until its observation expires. */ }
      }));
      if (current.signal.aborted) return;
      controller = undefined;
      const now = Date.now();
      onScheduleChanged(mergeSportsObservations(...Array.from(snapshots.values(), value =>
        value.events.filter(event => curatedEventFresh(event, now)))));
    };
    void refresh();
    const timer = window.setInterval(() => { void refresh(); }, 60_000);
    document.addEventListener("visibilitychange", refresh);
    return () => {
      controller?.abort();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refresh);
    };
  }, [followedCompetitionsKey, onScheduleChanged]);

  useEffect(() => {
    if (!competition || competition.status !== "configured") return;
    const timer = setInterval(() => {
      if (document.visibilityState !== "visible") return;
      setNow(Date.now());
      if (Date.now() >= nextRefresh.current) {
        nextRefresh.current = Date.now() + 60_000;
        setRefresh(value => value + 1);
      }
    }, 30_000);
    return () => clearInterval(timer);
  }, [competition, period]);

  if (!catalog?.enabled) return null;
  const followed = (type: "league" | "team", id: string) => follows.some(item => item.enabled && item.provider === "espn" && item.type === type && item.providerId === id);
  const follow = async (type: "league" | "team", id: string) => {
    setFollowing(true);
    try { await onFollow(type, id, "espn"); }
    catch { setError("Atlas could not save this follow. Please try again."); }
    finally { setFollowing(false); }
  };
  const request = async (event: SportsEvent) => {
    setPendingEvent(event.providerEventId); setError(null);
    try { await onRequestEvent({ provider: event.provider, providerEventId: event.providerEventId }); }
    catch { setError("Atlas could not confirm this event follow. Refresh before trying again."); }
    finally { setPendingEvent(null); }
  };
  const watchLive = async (event: SportsEvent) => {
    setPendingEvent(event.providerEventId); setPlaybackMessage(null);
    try {
      const available = await loadSportsLiveAvailability(event.provider, event.providerEventId);
      if (available.available && available.atlasChannelId) await onWatchLive(available.atlasChannelId);
      else setPlaybackMessage({ eventId: event.providerEventId, message: "Atlas has no available channel for this event yet." });
    } catch {
      setPlaybackMessage({ eventId: event.providerEventId, message: "Atlas could not check playback availability. Please try again." });
    }
    finally { setPendingEvent(null); }
  };
  const unsupported = competition?.status === "unsupported";
  const enabled = competition?.status === "configured";
  return (
    <section aria-labelledby="curated-sports-title" className="requests-message-panel">
      <p className="portal-page-eyebrow">Schedules</p>
      <h2 id="curated-sports-title">Browse Sports schedules</h2>
      <p>Choose a competition and date. Team filters use the loaded schedule. Follow an event, either team, or the competition to see Watch Live when a feed is available. Following does not record events.</p>
      <label>Sport and competition <select value={competitionId} onChange={event => { setTeamId(""); setCompetitionId(event.target.value); setError(null); }}>
        {Array.from(new Set(catalog.competitions.map(item => item.sport))).map(sport => (
          <optgroup key={sport} label={sport}>{catalog.competitions.filter(item => item.sport === sport).map(item => (
            <option key={item.id} value={item.id}>{item.name}{item.status === "unsupported" ? " — coverage pending" : item.status === "disabled" ? " — not enabled" : ""}</option>
          ))}</optgroup>
        ))}
      </select></label>{" "}
      <label>Date <select value={period} onChange={event => setPeriod(event.target.value as CuratedPeriod)}>
        <option value="today">Today</option><option value="tomorrow">Tomorrow</option><option value="week">Upcoming next 7 days</option>
      </select></label>{" "}
      <label>Team <select value={teamId} onChange={event => setTeamId(event.target.value)} disabled={!teams?.teams.length}>
        <option value="">All teams</option>{teams?.teams.map(team => <option key={team.id} value={team.id}>{team.name}</option>)}
      </select></label>
      {enabled && competition?.providerLeagueId ? <p>
        <button type="button" className="requests-refresh-button" disabled={following || followed("league", competition.providerLeagueId)} onClick={() => { void follow("league", competition.providerLeagueId!); }}>
          {followed("league", competition.providerLeagueId) ? "Following competition" : "Follow competition"}
        </button>{" "}
        {teamId ? <button type="button" className="requests-refresh-button" disabled={following || teams?.status !== "ready" || followed("team", teamId)} onClick={() => { void follow("team", teamId); }}>
          {followed("team", teamId) ? "Following team" : "Follow team"}
        </button> : null}{" "}
        <button type="button" className="requests-refresh-button" disabled={busy || now < refreshAt} onClick={() => { if (Date.now() >= nextRefresh.current) setRefresh(value => value + 1); }}>Refresh schedule</button>
      </p> : null}
      {unsupported ? <p>Schedule coverage for this competition has not been enabled. Use discovery below while coverage is reviewed.</p> : !enabled ? <p>This competition is not enabled yet.</p> : <>
        {busy ? <p role="status">Loading shared schedule…</p> : null}
        {error ? <p role="status">{error}</p> : null}
        {snapshot ? <>
          <p>Source: ESPN. Times use your device timezone ({Intl.DateTimeFormat().resolvedOptions().timeZone}). {snapshot.observedAt ? `Last observed: ${new Date(snapshot.observedAt).toLocaleString()}.` : "No completed observation yet."}</p>
          {snapshot.status !== "ready" || snapshot.retained || (!!snapshot.expiresAt && Date.parse(snapshot.expiresAt) <= now) ? <p role="status">Schedule status: {snapshot.status}. Coverage may be incomplete or out of date. Loaded events remain available.</p> : null}
          {period === "week" ? <p>This window starts now and excludes games whose scheduled start has passed. Choose Today for games already started.</p> : null}
          {events.length ? <div className="requests-grid">{events.map(event => {
            const check = availability[`${event.provider}:${event.providerEventId}`];
            const eventFollowed = follows.some(follow => follow.type === "event" && matchesSportsFollow(event, follow));
            const awaitingPlayback = inPlaybackWindow(event, now) && follows.some(follow => matchesSportsFollow(event, follow));
            const canWatch = awaitingPlayback && check?.available === true && Boolean(check.atlasChannelId);
            return <article className="requests-message-panel" key={event.providerEventId}>
              <h3>{event.name}</h3>
              <p><time dateTime={event.startAt}>{curatedStartLabel(event.startAt)}</time></p>
              <p>{curatedEventFresh(event, now) ? event.status : `Last reported: ${event.status} — status needs refresh`}</p>
              {event.metadataObservedAt ? <p>Status observed: {curatedStartLabel(event.metadataObservedAt)}</p> : null}
              {event.status === "scheduled" && Date.parse(event.startAt) <= now ? <p>Scheduled start has passed; waiting for an updated provider status.</p> : null}
              {([event.awayTeamId, event.homeTeamId].filter((id): id is string => Boolean(id))).map(id => {
                const name = teams?.teams.find(team => team.id === id)?.name ?? "team";
                return <button key={id} type="button" className="requests-refresh-button"
                  disabled={following || teams?.status !== "ready" || followed("team", id)}
                  onClick={() => { void follow("team", id); }}>
                  {followed("team", id) ? `Following ${name}` : `Follow ${name}`}
                </button>;
              })}
              <button type="button" className="requests-refresh-button"
                disabled={pendingEvent !== null || eventFollowed}
                onClick={() => { void request(event); }}>
                {eventFollowed ? "Following event" : "Follow event"}
              </button>
              {canWatch ? <button type="button" className="requests-refresh-button"
                disabled={pendingEvent !== null} onClick={() => { void watchLive(event); }}>
                Watch Live
              </button> : awaitingPlayback && playbackMessage?.eventId !== event.providerEventId ? <p>Waiting for a live feed.</p> : null}
              {playbackMessage?.eventId === event.providerEventId ? <p role="status">{playbackMessage.message}</p> : null}
              <p>Recording is unavailable for ESPN schedule-only events.</p>
            </article>;
          })}</div> : snapshot.coverageComplete ? <p>No events in the loaded schedule match this selection.</p> : <p>The schedule is being prepared or is temporarily unavailable. This does not confirm that there are no events.</p>}
        </> : null}
      </>}
      <p>Configured channels and their guide information are listed in the channels section below. Schedule listings do not establish stream availability.</p>
    </section>
  );
}
