"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useFavorites } from "../../favorites";
import { listSavedResumes, type SavedResume } from "../../playback/services/continuity";
import { episodeHref } from "../../playback/services/episode-navigation";
import { loadSportsFollows, type SportsFollow } from "../../sports";
import { sportsLocalStart } from "../../sports/services/currentlyLive";
import { curatedEventFresh } from "../../sports/services/curatedLiveState";
import {
  loadCuratedCatalog, loadCuratedSchedule, retainCuratedSchedule,
  type CuratedCompetition, type CuratedSchedule
} from "../../sports/services/curatedSchedule";
import { selectedUpcomingSchedule } from "../../sports/services/upcomingSchedule";
import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";
import { PORTAL_ROUTES } from "../../../lib/navigation/portal";

function positionLabel(seconds: number): string {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

function ContinueWatching({ userId }: { userId: string }): React.ReactElement {
  const [items, setItems] = useState<readonly SavedResume[] | null>(null);

  useEffect(() => {
    function refresh(): void {
      try { setItems(listSavedResumes(window.localStorage, userId)); }
      catch { setItems([]); }
    }

    window.addEventListener("pageshow", refresh);
    window.addEventListener("storage", refresh);
    const initial = window.setTimeout(refresh, 0);
    return () => {
      window.clearTimeout(initial);
      window.removeEventListener("pageshow", refresh);
      window.removeEventListener("storage", refresh);
    };
  }, [userId]);

  return (
    <section className="portal-home-card" aria-labelledby="home-resume">
      <h3 id="home-resume">Continue watching</h3>
      {items === null ? <p role="status">Checking saved playback…</p> : items.length ? (
        <ul>
          {items.slice(0, 4).map(item => (
            <li key={JSON.stringify([item.provider, item.itemId])}>
              <strong>{item.title}</strong>
              <p>{positionLabel(item.position)} watched on this browser</p>
              {item.duration && <progress aria-label={`Watch progress for ${item.title}`} max={item.duration} value={item.position} />}
              <Link className="requests-refresh-button" href={episodeHref(item.provider, item.itemId)}>
                {item.episode ? "Resume episode" : "Resume playback"}
              </Link>
            </li>
          ))}
        </ul>
      ) : <p>No saved titles on this browser. <Link href={`${PORTAL_ROUTES.media.path}?view=library`}>Open Library</Link></p>}
    </section>
  );
}

function matchesCompetition(follow: SportsFollow, competition: CuratedCompetition): boolean {
  const league = competition.providerLeagueId;
  if (!follow.enabled || follow.provider !== competition.provider || !league || follow.type === "channel") return false;
  if (follow.type === "league") return follow.providerId === league;
  const prefix = league.replaceAll("/", "-") + "-";
  return follow.providerId.startsWith(prefix) && /^\d+$/.test(follow.providerId.slice(prefix.length));
}

function FollowedSports(): React.ReactElement {
  const [follows, setFollows] = useState<readonly SportsFollow[] | null>(null);
  const [schedules, setSchedules] = useState<Record<string, CuratedSchedule>>({});
  const [failed, setFailed] = useState<Record<string, boolean>>({});
  const [now, setNow] = useState(0);
  const [unavailable, setUnavailable] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const timers = new Set<ReturnType<typeof setTimeout>>();

    async function refresh(competition: string): Promise<void> {
      let delay = 60_000;
      if (document.visibilityState !== "hidden") {
        try {
          const incoming = await loadCuratedSchedule(competition, "week", controller.signal);
          if (controller.signal.aborted) return;
          setSchedules(current => ({
            ...current, [competition]: retainCuratedSchedule(current[competition] ?? null, incoming)
          }));
          setFailed(current => ({ ...current, [competition]: false }));
          delay = Math.max(delay, incoming.retryAfterSeconds * 1000);
        } catch {
          if (controller.signal.aborted) return;
          setFailed(current => ({ ...current, [competition]: true }));
        }
        setNow(Date.now());
      }
      const timer = setTimeout(() => {
        timers.delete(timer);
        void refresh(competition);
      }, delay);
      timers.add(timer);
    }

    void Promise.all([
      loadSportsFollows({ signal: controller.signal }),
      loadCuratedCatalog(controller.signal)
    ]).then(([saved, catalog]) => {
      if (controller.signal.aborted) return;
      setFollows(saved);
      for (const competition of catalog.competitions) {
        if (competition.status === "configured" && saved.some(follow => matchesCompetition(follow, competition))) {
          void refresh(competition.id);
        }
      }
    }).catch(() => {
      if (!controller.signal.aborted) setUnavailable(true);
    });

    return () => { controller.abort(); timers.forEach(timer => clearTimeout(timer)); };
  }, []);

  useEffect(() => {
    const expiries = Object.values(schedules).flatMap(schedule => schedule.events.map(event =>
      Date.parse(event.metadataExpiresAt ?? "")
    )).filter(expiry => expiry > now);
    if (!expiries.length) return;
    const timer = setTimeout(() => setNow(Date.now()), Math.max(1, Math.min(...expiries) - Date.now()));
    return () => clearTimeout(timer);
  }, [schedules, now]);

  const snapshots = Object.values(schedules);
  const events = selectedUpcomingSchedule(
    Object.fromEntries(snapshots.map(schedule => [schedule.competitionId, {
      events: schedule.events, loadedAt: Date.parse(schedule.evaluatedAt)
    }])),
    follows ?? [], undefined, now
  ).slice(0, 4);
  const scheduleUnavailable = unavailable || Object.values(failed).some(Boolean) ||
    snapshots.some(schedule => schedule.status === "unavailable");
  return (
    <section className="portal-home-card" aria-labelledby="home-sports">
      <h3 id="home-sports">Followed Sports</h3>
      {scheduleUnavailable && <p role="status">Schedule refresh is unavailable. Last known times may have changed.</p>}
      {events.length ? (
        <ul>{events.map(event => {
          const snapshot = snapshots.find(schedule => schedule.providerLeagueId === event.providerLeagueId);
          const lastKnown = !curatedEventFresh(event, now) || snapshot?.retained ||
            (snapshot && failed[snapshot.competitionId]);
          return (
            <li key={JSON.stringify([event.provider, event.providerEventId])}>
              <strong>{event.name}</strong>
              <p>{lastKnown ? "Last known time" : "Scheduled"} · <time dateTime={event.startAt}>{sportsLocalStart(event.startAt)}</time></p>
            </li>
          );
        })}</ul>
      ) : <p>{follows === null && !unavailable ? "Loading follows…" : "No upcoming followed events in the shared schedule."}</p>}
      <Link href={PORTAL_ROUTES.sports.path}>Open Sports and manage follows</Link>
    </section>
  );
}

function FollowedMedia(): React.ReactElement {
  const { state } = useFavorites();
  return (
    <section className="portal-home-card" aria-labelledby="home-favorites">
      <h3 id="home-favorites">Followed media</h3>
      {state.status === "ready" && state.data.length ? (
        <ul>{state.data.slice(0, 4).map(item => (
          <li key={item.favoriteId}>{item.title ?? "Saved title"}</li>
        ))}</ul>
      ) : <p>{state.status === "loading" ? "Loading favorites…" : state.status === "error" ? "Favorites are unavailable." : "No saved favorites yet."}</p>}
      <Link href={PORTAL_ROUTES.favorites.path}>Open Favorites</Link>
    </section>
  );
}

export function PortalHome({ userId }: { userId: string }): React.ReactElement {
  const { can } = usePermission();
  return (
    <div className="portal-home-grid">
      {can(ATLAS_PERMISSIONS.mediaRead) && <ContinueWatching userId={userId} />}
      {can(ATLAS_PERMISSIONS.sportsRead) && <FollowedSports />}
      {can(ATLAS_PERMISSIONS.favoritesRead) && <FollowedMedia />}
    </div>
  );
}
