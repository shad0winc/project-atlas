import { AtlasApiError } from "../../../lib/api/errors";
import {
  authenticatedAtlasApiRequest,
  authenticatedAtlasApiRequestWithMetadata
} from "../../../lib/services/authenticated";

import type {
  SubtitleSelection
} from "../../playback/services/session";
import type {
  PlaybackSession,
  PlaybackTrack
} from "../../playback/types/session";

import {
  createSportsEventCollection,
  createSportsEventSearchCollection,
  createSportsFollow,
  createSportsFollowCollection,
  createSportsSearchCollection,
  createSportsSubscription,
  type SportsEvent,
  type SportsEventCollectionTransport,
  type SportsFollow,
  type SportsFollowCollectionTransport,
  type SportsFollowTransport,
  type SportsSearchCollectionTransport,
  type SportsSearchResult,
  type SportsSearchType,
  type SportsSubscription,
  type SportsSubscriptionTransport
} from "../types/sports";

export type SportsEventRequestInput = Readonly<{
  provider: string;
  providerEventId: string;
}>;

export type SportsRequestOptions = Readonly<{
  signal?: AbortSignal;
}>;

export type SportsEventFilter = Readonly<{
  provider?: string;
  eventIds?: readonly string[];
  teamIds?: readonly string[];
  leagueIds?: readonly string[];
}>;

export type SportsLiveAvailability = Readonly<{
  available: boolean;
  atlasChannelId: string | null;
}>;

type SportsPlaybackTrackTransport = Readonly<{
  index: number;
  kind: "audio" | "subtitle";
  label: string;
  language: string | null;
  codec: string | null;
  default: boolean;
  forced: boolean;
}>;

type SportsLivePlaybackSessionTransport = Readonly<{
  available: boolean;
  action: "watch_now" | "watch_live" | "watch_recording";
  label: string;
  backend: string;
  source_type: "library" | "live" | "recording";
  provider: string;
  requested_target_id: string;
  playable_target_id: string;
  title: string;
  media_type: string;
  duration_ticks: number | null;
  can_seek: boolean;
  playback_bootstrap_url: string;
  playback_capability: string;
  audio_tracks: readonly SportsPlaybackTrackTransport[];
  subtitle_tracks: readonly SportsPlaybackTrackTransport[];
  previous_target_id: string | null;
  next_target_id: string | null;
}>;

export type SportsLiveSessionResult = Readonly<{
  atlasChannelId: string;
  session: PlaybackSession;
  liveSessionId: string;
  ttlSeconds: number;
}>;

type SportsLiveHeartbeatTransport = Readonly<{
  session_id: string;
  ttl_seconds: number;
}>;

export type SportsLiveHeartbeatResult = Readonly<{
  liveSessionId: string;
  ttlSeconds: number;
}>;

type SportsLiveAvailabilityTransport = Readonly<{
  available: boolean;
  atlas_channel_id: string | null;
}>;

function mapSportsPlaybackTrack(
  track: SportsPlaybackTrackTransport
): PlaybackTrack {
  return Object.freeze({
    index: track.index,
    kind: track.kind,
    label: track.label,
    ...(track.language === null
      ? {}
      : { language: track.language }),
    ...(track.codec === null
      ? {}
      : { codec: track.codec }),
    default: track.default,
    forced: track.forced
  });
}

function mapSportsLivePlaybackSession(
  response: SportsLivePlaybackSessionTransport
): PlaybackSession {
  if (
    response.action !== "watch_live" ||
    response.source_type !== "live"
  ) {
    throw new Error(
      "Sports live playback response was not a live session."
    );
  }

  return Object.freeze({
    available: response.available,
    action: response.action,
    label: response.label,
    backend: response.backend,
    sourceType: response.source_type,
    provider: response.provider,
    requestedTargetId: response.requested_target_id,
    playableTargetId: response.playable_target_id,
    title: response.title,
    mediaType: response.media_type,
    ...(response.duration_ticks === null
      ? {}
      : { durationTicks: response.duration_ticks }),
    canSeek: response.can_seek,
    playbackBootstrapUrl:
      response.playback_bootstrap_url,
    playbackCapability:
      response.playback_capability,
    audioTracks:
      response.audio_tracks.map(
        mapSportsPlaybackTrack
      ),
    subtitleTracks:
      response.subtitle_tracks.map(
        mapSportsPlaybackTrack
      ),
    ...(response.previous_target_id === null
      ? {}
      : {
          previousTargetId:
            response.previous_target_id
        }),
    ...(response.next_target_id === null
      ? {}
      : {
          nextTargetId:
            response.next_target_id
        })
  });
}

export async function loadSportsEvents(options: SportsRequestOptions = {}, filter: SportsEventFilter = {}): Promise<readonly SportsEvent[]> {
  const params = new URLSearchParams({
    provider: filter.provider?.trim() || "thesportsdb"
  });
  for (const id of filter.eventIds ?? []) {
    if (id.trim()) params.append("provider_event_id", id.trim());
  }
  for (const id of filter.teamIds ?? []) if (id.trim()) params.append("team_id", id.trim());
  for (const id of filter.leagueIds ?? []) if (id.trim()) params.append("league_id", id.trim());
  const response = await authenticatedAtlasApiRequest<SportsEventCollectionTransport>(
    `/sports/events?${params.toString()}`,
    {
      method: "GET",
      cache: "no-store",
      signal: options.signal
    }
  );

  return createSportsEventCollection(response);
}

export async function loadSportsLiveAvailability(
  provider: string,
  providerEventId: string,
  options: SportsRequestOptions = {}
): Promise<SportsLiveAvailability> {
  const normalizedProvider = provider.trim();
  const normalizedEventId = providerEventId.trim();

  if (!normalizedProvider) {
    throw new Error(
      "sportsLiveAvailability.provider must not be empty."
    );
  }

  if (!normalizedEventId) {
    throw new Error(
      "sportsLiveAvailability.providerEventId must not be empty."
    );
  }

  const params = new URLSearchParams({
    provider: normalizedProvider,
    provider_event_id: normalizedEventId
  });

  const response =
    await authenticatedAtlasApiRequest<SportsLiveAvailabilityTransport>(
      `/sports/live/availability?${params.toString()}`,
      {
        method: "GET",
        cache: "no-store",
        signal: options.signal
      }
    );

  const available = Boolean(response.available);

  const atlasChannelId =
    typeof response.atlas_channel_id === "string" &&
    response.atlas_channel_id.trim()
      ? response.atlas_channel_id.trim()
      : null;

  if (!available && atlasChannelId !== null) {
    throw new Error(
      "Sports live availability returned an unsafe unavailable channel."
    );
  }

  if (available && atlasChannelId === null) {
    throw new Error(
      "Sports live availability did not return a channel."
    );
  }

  return Object.freeze({
    available,
    atlasChannelId
  });
}

export async function createSportsLiveSession(
  atlasChannelId: string,
  options: SportsRequestOptions = {},
  subtitle: SubtitleSelection = "auto"
): Promise<SportsLiveSessionResult> {
  const normalizedChannelId = atlasChannelId.trim();

  if (!normalizedChannelId) {
    throw new Error(
      "sportsLiveSession.atlasChannelId must not be empty."
    );
  }

  const subtitleValue =
    typeof subtitle === "number"
      ? String(subtitle)
      : subtitle;

  const query = new URLSearchParams();

  if (subtitleValue !== "auto") {
    query.set("subtitle", subtitleValue);
  }

  const suffix =
    query.size === 0
      ? ""
      : `?${query.toString()}`;

  const response =
    await authenticatedAtlasApiRequestWithMetadata<
      SportsLivePlaybackSessionTransport
    >(
      `/sports/live/${encodeURIComponent(
        normalizedChannelId
      )}/session${suffix}`,
      {
        method: "GET",
        cache: "no-store",
        signal: options.signal,
        retryPolicy: {
          maxRetries: 0,
          baseDelayMs: 250,
          maxDelayMs: 5_000
        }
      }
    );

  const liveSessionId =
    response.headers
      .get("X-Atlas-Live-Session-ID")
      ?.trim() ?? "";

  if (!liveSessionId) {
    throw new Error(
      "Sports live session did not return a lease ID."
    );
  }

  try {
    const ttlHeader =
      response.headers
        .get("X-Atlas-Live-Session-TTL")
        ?.trim() ?? "";

    const ttlSeconds = Number(ttlHeader);

    if (
      !Number.isInteger(ttlSeconds) ||
      ttlSeconds <= 0
    ) {
      throw new Error(
        "Sports live session did not return a valid TTL."
      );
    }

    const session =
      mapSportsLivePlaybackSession(
        response.data
      );

    return Object.freeze({
      atlasChannelId: normalizedChannelId,
      session,
      liveSessionId,
      ttlSeconds
    });
  } catch (validationError) {
    try {
      await releaseSportsLiveSession(
        liveSessionId
      );
    } catch {
      // Preserve the original validation failure.
      // Server TTL remains the final fail-safe.
    }

    throw validationError;
  }
}

export async function heartbeatSportsLiveSession(
  liveSessionId: string,
  options: SportsRequestOptions = {}
): Promise<SportsLiveHeartbeatResult> {
  const normalizedSessionId = liveSessionId.trim();

  if (!normalizedSessionId) {
    throw new Error(
      "sportsLiveSession.liveSessionId must not be empty."
    );
  }

  const response =
    await authenticatedAtlasApiRequest<
      SportsLiveHeartbeatTransport
    >(
      `/sports/live/sessions/${encodeURIComponent(
        normalizedSessionId
      )}/heartbeat`,
      {
        method: "POST",
        cache: "no-store",
        signal: options.signal,
        retryPolicy: {
          maxRetries: 0,
          baseDelayMs: 250,
          maxDelayMs: 5_000
        }
      }
    );

  const returnedSessionId =
    typeof response.session_id === "string"
      ? response.session_id.trim()
      : "";

  if (
    !returnedSessionId ||
    returnedSessionId !== normalizedSessionId
  ) {
    throw new Error(
      "Sports live heartbeat returned an unexpected session ID."
    );
  }

  const ttlSeconds = response.ttl_seconds;

  if (
    !Number.isInteger(ttlSeconds) ||
    ttlSeconds <= 0
  ) {
    throw new Error(
      "Sports live heartbeat returned an invalid TTL."
    );
  }

  return Object.freeze({
    liveSessionId: returnedSessionId,
    ttlSeconds
  });
}

export async function releaseSportsLiveSession(
  liveSessionId: string,
  options: SportsRequestOptions = {}
): Promise<void> {
  const normalizedSessionId = liveSessionId.trim();

  if (!normalizedSessionId) {
    throw new Error(
      "sportsLiveSession.liveSessionId must not be empty."
    );
  }

  await authenticatedAtlasApiRequest<void>(
    `/sports/live/sessions/${encodeURIComponent(
      normalizedSessionId
    )}`,
    {
      method: "DELETE",
      cache: "no-store",
      signal: options.signal,
      retryPolicy: {
        maxRetries: 0,
        baseDelayMs: 250,
        maxDelayMs: 5_000
      }
    }
  );
}

export async function requestSportsEvent(
  input: SportsEventRequestInput,
  options: SportsRequestOptions = {}
): Promise<SportsSubscription> {
  const provider = input.provider.trim();
  const providerEventId = input.providerEventId.trim();

  if (!provider) {
    throw new Error("sportsRequest.provider must not be empty.");
  }

  if (!providerEventId) {
    throw new Error("sportsRequest.providerEventId must not be empty.");
  }

  const response = await authenticatedAtlasApiRequest<SportsSubscriptionTransport>(
    "/sports/subscriptions",
    {
      method: "POST",
      cache: "no-store",
      signal: options.signal,
      body: {
        provider,
        provider_event_id: providerEventId
      },
      retryPolicy: {
        maxRetries: 0,
        baseDelayMs: 250,
        maxDelayMs: 5_000
      }
    }
  );

  return createSportsSubscription(response);
}

export async function searchSports(
  type: SportsSearchType,
  query: string,
  options: SportsRequestOptions = {}
): Promise<readonly SportsSearchResult[]> {
  const normalizedQuery = query.trim();

  if (!normalizedQuery) {
    return [];
  }

  const path = type === "team" ? "teams" : type === "league" ? "leagues" : "events";

  try {
    const requestOptions = {
      method: "GET" as const,
      cache: "no-store" as const,
      signal: options.signal,
      retryPolicy: {
        maxRetries: 0,
        baseDelayMs: 250,
        maxDelayMs: 5_000
      }
    };

    if (type === "event") {
      const response =
        await authenticatedAtlasApiRequest<SportsEventCollectionTransport>(
          `/sports/search/${path}?provider=thesportsdb&query=${encodeURIComponent(normalizedQuery)}`,
          requestOptions
        );
      return createSportsEventSearchCollection(response);
    }

    const response =
      await authenticatedAtlasApiRequest<SportsSearchCollectionTransport>(
        `/sports/search/${path}?provider=thesportsdb&query=${encodeURIComponent(normalizedQuery)}`,
        requestOptions
      );

    return createSportsSearchCollection(type, response);
  } catch (error) {
    if (
      error instanceof AtlasApiError &&
      error.kind === "rate-limit"
    ) {
      throw new Error(
        "Sports search is temporarily rate limited. "
          + "Please try again shortly."
      );
    }

    throw error;
  }
}

export async function loadSportsFollows(options: SportsRequestOptions = {}): Promise<readonly SportsFollow[]> { return createSportsFollowCollection(await authenticatedAtlasApiRequest<SportsFollowCollectionTransport>("/sports/follows", { method: "GET", cache: "no-store", signal: options.signal })); }
export async function followSports(type: "event" | "team" | "league", providerId: string, options: SportsRequestOptions = {}): Promise<SportsFollow> {
  const id=providerId.trim(); if (!id) throw new Error("sportsFollow.providerId must not be empty.");
  return createSportsFollow(await authenticatedAtlasApiRequest<SportsFollowTransport>("/sports/follows", { method: "POST", cache: "no-store", signal: options.signal, body: { type, provider: "thesportsdb", provider_id: id }, retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5000 } }));
}
export async function unfollowSports(subscriptionId: string, options: SportsRequestOptions = {}): Promise<void> {
  const id=subscriptionId.trim(); if (!id) throw new Error("sportsFollow.subscriptionId must not be empty.");
  await authenticatedAtlasApiRequest<unknown>(`/sports/follows/${encodeURIComponent(id)}`, { method: "DELETE", cache: "no-store", signal: options.signal });
}

export async function updateSportsRecordingIntent(
  subscriptionId: string,
  record: boolean,
  options: SportsRequestOptions = {}
): Promise<SportsFollow> {
  const id = subscriptionId.trim();
  if (!id) throw new Error("sportsFollow.subscriptionId must not be empty.");
  return createSportsFollow(
    await authenticatedAtlasApiRequest<SportsFollowTransport>(
      `/sports/follows/${encodeURIComponent(id)}/recording`,
      { method: "PATCH", cache: "no-store", signal: options.signal, body: { record },
        retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5_000 } }
    )
  );
}
