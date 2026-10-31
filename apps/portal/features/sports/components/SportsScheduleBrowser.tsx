"use client";

import { useEffect, useRef, useState } from "react";
import type { SportsFollow } from "../types/sports";
import {
  filterCuratedTeam, loadCuratedCatalog, loadCuratedSchedule, loadCuratedTeams,
  retainCuratedSchedule, type CuratedCatalog, type CuratedPeriod,
  type CuratedSchedule, type CuratedTeams,
} from "../services/curatedSchedule";

type Props = Readonly<{
  follows: readonly SportsFollow[];
  onFollow: (type: "team" | "league", id: string, provider: string) => Promise<void>;
}>;

export function SportsScheduleBrowser({ follows, onFollow }: Props): React.ReactElement | null {
  const [catalog, setCatalog] = useState<CuratedCatalog | null>(null);
  const [competitionId, setCompetitionId] = useState("");
  const [period, setPeriod] = useState<CuratedPeriod>("today");
  const [teamId, setTeamId] = useState("");
  const [directory, setDirectory] = useState<CuratedTeams | null>(null);
  const [result, setResult] = useState<Readonly<{ key: string; snapshot: CuratedSchedule }> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [following, setFollowing] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const nextRefresh = useRef(0);
  const [refreshAt, setRefreshAt] = useState(0);
  const [now, setNow] = useState(Date.now);
  const key = `${competitionId}:${period}`;
  const competition = catalog?.competitions.find(item => item.id === competitionId);
  const snapshot = result?.key === key ? result.snapshot : null;
  const teams = directory?.competitionId === competitionId ? directory : null;
  const events = filterCuratedTeam(snapshot, teamId);

  useEffect(() => {
    const controller = new AbortController();
    void loadCuratedCatalog(controller.signal).then(value => {
      if (controller.signal.aborted) return;
      setCatalog(value);
      setCompetitionId(value.competitions.find(item => item.status === "configured")?.id ?? value.competitions[0]?.id ?? "");
    }).catch(() => { /* Existing Sports remains available when this optional surface is unavailable. */ });
    return () => controller.abort();
  }, []);

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

  if (!catalog?.enabled) return null;
  const followed = (type: "league" | "team", id: string) => follows.some(item => item.enabled && item.provider === "espn" && item.type === type && item.providerId === id);
  const follow = async (type: "league" | "team", id: string) => {
    setFollowing(true);
    try { await onFollow(type, id, "espn"); }
    catch { setError("Atlas could not save this follow. Please try again."); }
    finally { setFollowing(false); }
  };
  const unsupported = competition?.status === "unsupported";
  const enabled = competition?.status === "configured";
  return (
    <section aria-labelledby="curated-sports-title" className="requests-message-panel">
      <p className="portal-page-eyebrow">Schedules</p>
      <h2 id="curated-sports-title">Browse Sports schedules</h2>
      <p>Choose a competition and date. Team filters use the loaded schedule. Following saves your selection and does not record events.</p>
      <label>Sport and competition <select value={competitionId} onChange={event => { setTeamId(""); setCompetitionId(event.target.value); setError(null); }}>
        {Array.from(new Set(catalog.competitions.map(item => item.sport))).map(sport => (
          <optgroup key={sport} label={sport}>{catalog.competitions.filter(item => item.sport === sport).map(item => (
            <option key={item.id} value={item.id}>{item.name}{item.status === "unsupported" ? " — coverage pending" : item.status === "disabled" ? " — not enabled" : ""}</option>
          ))}</optgroup>
        ))}
      </select></label>{" "}
      <label>Date <select value={period} onChange={event => setPeriod(event.target.value as CuratedPeriod)}>
        <option value="today">Today</option><option value="tomorrow">Tomorrow</option><option value="week">Next 7 days</option>
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
          <p>Source: ESPN. Times use your device timezone. {snapshot.observedAt ? `Last observed: ${new Date(snapshot.observedAt).toLocaleString()}.` : "No completed observation yet."}</p>
          {snapshot.status !== "ready" || snapshot.retained || (!!snapshot.expiresAt && Date.parse(snapshot.expiresAt) <= now) ? <p role="status">Schedule status: {snapshot.status}. Coverage may be incomplete or out of date. Loaded events remain available.</p> : null}
          {events.length ? <div className="requests-grid">{events.map(event => <article className="requests-message-panel" key={event.providerEventId}>
            <h3>{event.name}</h3><p>{new Date(event.startAt).toLocaleString()}</p><p>{event.status}</p>
          </article>)}</div> : snapshot.coverageComplete ? <p>No events in the loaded schedule match this selection.</p> : <p>The schedule is being prepared or is temporarily unavailable. This does not confirm that there are no events.</p>}
        </> : null}
      </>}
      <p>Configured channels and their guide information are listed in the channels section below. Schedule listings do not establish stream availability.</p>
    </section>
  );
}
