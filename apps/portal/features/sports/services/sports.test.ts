import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  authenticatedAtlasApiRequest: vi.fn(),
  authenticatedAtlasApiRequestWithMetadata: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: mocks.authenticatedAtlasApiRequest,
  authenticatedAtlasApiRequestWithMetadata:
    mocks.authenticatedAtlasApiRequestWithMetadata
}));

import {
  createSportsLiveSession,
  heartbeatSportsLiveSession,
  loadSportsEvents,
  loadSportsLiveAvailability,
  releaseSportsLiveSession,
  requestSportsEvent,
  searchSports
} from "./sports";

describe("Sports Portal service", () => {
  beforeEach(() => {
    mocks.authenticatedAtlasApiRequest.mockReset();
    mocks.authenticatedAtlasApiRequestWithMetadata.mockReset();
  });

  it("loads authenticated Sports events", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      events: [
        {
          provider: "thesportsdb",
          provider_event_id: "event-001",
          name: "Atlas United vs Atlas City",
          sport: "Soccer",
          league: "Atlas Test League",
          start_at: "2026-08-17T20:00:00Z",
          status: "scheduled",
          requested: false
        }
      ]
    });

    const events = await loadSportsEvents();

    expect(mocks.authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/events?provider=thesportsdb",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );

    expect(events).toHaveLength(1);

    expect(events[0]?.providerEventId).toBe("event-001");
  });

  it("loads exact followed-event metadata by provider event ID", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      events: []
    });

    await loadSportsEvents(
      {},
      {
        provider: "thesportsdb",
        eventIds: ["event-001", "event-002"]
      }
    );

    expect(mocks.authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/events?provider=thesportsdb"
        + "&provider_event_id=event-001"
        + "&provider_event_id=event-002",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );
  });

  it("loads authoritative Sports live availability", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      available: true,
      atlas_channel_id: "sports-live-source-001"
    });

    const availability = await loadSportsLiveAvailability(
      "thesportsdb",
      "event-001"
    );

    expect(
      mocks.authenticatedAtlasApiRequest
    ).toHaveBeenCalledWith(
      "/sports/live/availability?provider=thesportsdb&provider_event_id=event-001",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );

    expect(availability).toEqual({
      available: true,
      atlasChannelId: "sports-live-source-001"
    });
  });

  it("creates a Sports live session with the authoritative lease", async () => {
    mocks.authenticatedAtlasApiRequestWithMetadata.mockResolvedValue({
      data: {
        available: true,
        action: "watch_live",
        label: "Watch Live",
        backend: "jellyfin",
        source_type: "live",
        provider: "jellyfin",
        requested_target_id: "sports-live-source-001",
        playable_target_id: "jellyfin-live-item-001",
        title: "Atlas United vs Atlas City",
        media_type: "Video",
        duration_ticks: null,
        can_seek: false,
        playback_bootstrap_url:
          "https://playback.shadowinc.co/_atlas/playback/bootstrap",
        playback_capability: "sports-capability",
        audio_tracks: [],
        subtitle_tracks: [],
        previous_target_id: null,
        next_target_id: null
      },
      status: 200,
      requestId: "sports-live-request-001",
      headers: new Headers({
        "X-Atlas-Live-Session-ID": "live-session-001",
        "X-Atlas-Live-Session-TTL": "90"
      })
    });

    const result = await createSportsLiveSession(
      "sports-live-source-001"
    );

    expect(
      mocks.authenticatedAtlasApiRequestWithMetadata
    ).toHaveBeenCalledWith(
      "/sports/live/sports-live-source-001/session",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );

    expect(result.liveSessionId).toBe(
      "live-session-001"
    );

    expect(result.ttlSeconds).toBe(90);

    expect(result.session).toEqual({
      available: true,
      action: "watch_live",
      label: "Watch Live",
      backend: "jellyfin",
      sourceType: "live",
      provider: "jellyfin",
      requestedTargetId: "sports-live-source-001",
      playableTargetId: "jellyfin-live-item-001",
      title: "Atlas United vs Atlas City",
      mediaType: "Video",
      canSeek: false,
      playbackBootstrapUrl:
        "https://playback.shadowinc.co/_atlas/playback/bootstrap",
      playbackCapability: "sports-capability",
      audioTracks: [],
      subtitleTracks: []
    });
  });

  it("preserves Atlas channel identity separately from the Jellyfin playback target", async () => {
    mocks.authenticatedAtlasApiRequestWithMetadata.mockResolvedValue({
      data: {
        available: true,
        action: "watch_live",
        label: "Watch Live",
        backend: "jellyfin",
        source_type: "live",
        provider: "jellyfin",
        requested_target_id: "jf-channel-exact",
        playable_target_id: "jf-channel-exact",
        title: "Atlas Test Channel",
        media_type: "video",
        duration_ticks: null,
        can_seek: false,
        playback_bootstrap_url:
          "https://playback.shadowinc.co/_atlas/playback/bootstrap",
        playback_capability: "sports-capability-real-identity",
        audio_tracks: [],
        subtitle_tracks: [],
        previous_target_id: null,
        next_target_id: null
      },
      status: 200,
      requestId: "sports-live-request-real-identity",
      headers: new Headers({
        "X-Atlas-Live-Session-ID": "live-session-real-identity",
        "X-Atlas-Live-Session-TTL": "90"
      })
    });

    const result = await createSportsLiveSession(
      "sports-event-001"
    );

    expect(result.atlasChannelId).toBe(
      "sports-event-001"
    );

    expect(result.session.requestedTargetId).toBe(
      "jf-channel-exact"
    );

    expect(result.session.playableTargetId).toBe(
      "jf-channel-exact"
    );

    expect(result.session.provider).toBe(
      "jellyfin"
    );
  });

  it("forwards Sports live subtitle selection through the lease route", async () => {
    mocks.authenticatedAtlasApiRequestWithMetadata.mockResolvedValue({
      data: {
        available: true,
        action: "watch_live",
        label: "Watch Live",
        backend: "jellyfin",
        source_type: "live",
        provider: "jellyfin",
        requested_target_id: "sports-live-source-001",
        playable_target_id: "jellyfin-live-item-001",
        title: "Atlas United vs Atlas City",
        media_type: "Video",
        duration_ticks: null,
        can_seek: false,
        playback_bootstrap_url:
          "https://playback.shadowinc.co/_atlas/playback/bootstrap",
        playback_capability: "sports-capability-subtitle",
        audio_tracks: [],
        subtitle_tracks: [],
        previous_target_id: null,
        next_target_id: null
      },
      status: 200,
      requestId: "sports-live-request-subtitle",
      headers: new Headers({
        "X-Atlas-Live-Session-ID": "live-session-subtitle",
        "X-Atlas-Live-Session-TTL": "90"
      })
    });

    await createSportsLiveSession(
      "sports-live-source-001",
      {},
      4
    );

    expect(
      mocks.authenticatedAtlasApiRequestWithMetadata
    ).toHaveBeenCalledWith(
      "/sports/live/sports-live-source-001/session?subtitle=4",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );

    mocks.authenticatedAtlasApiRequestWithMetadata.mockClear();

    await createSportsLiveSession(
      "sports-live-source-001",
      {},
      "off"
    );

    expect(
      mocks.authenticatedAtlasApiRequestWithMetadata
    ).toHaveBeenCalledWith(
      "/sports/live/sports-live-source-001/session?subtitle=off",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );

    mocks.authenticatedAtlasApiRequestWithMetadata.mockClear();

    await createSportsLiveSession(
      "sports-live-source-001",
      {},
      "auto"
    );

    expect(
      mocks.authenticatedAtlasApiRequestWithMetadata
    ).toHaveBeenCalledWith(
      "/sports/live/sports-live-source-001/session",
      expect.objectContaining({
        method: "GET",
        cache: "no-store"
      })
    );
  });

  it("releases an admitted Sports live lease when TTL validation fails", async () => {
    mocks.authenticatedAtlasApiRequestWithMetadata.mockResolvedValue({
      data: {
        available: true,
        action: "watch_live",
        label: "Watch Live",
        backend: "jellyfin",
        source_type: "live",
        provider: "jellyfin",
        requested_target_id: "jf-channel-exact",
        playable_target_id: "jf-channel-exact",
        title: "Atlas Test Channel",
        media_type: "video",
        duration_ticks: null,
        can_seek: false,
        playback_bootstrap_url:
          "https://playback.shadowinc.co/_atlas/playback/bootstrap",
        playback_capability: "sports-capability-invalid-ttl",
        audio_tracks: [],
        subtitle_tracks: [],
        previous_target_id: null,
        next_target_id: null
      },
      status: 200,
      requestId: "sports-live-invalid-ttl",
      headers: new Headers({
        "X-Atlas-Live-Session-ID": "live-session-invalid-ttl",
        "X-Atlas-Live-Session-TTL": "0"
      })
    });

    mocks.authenticatedAtlasApiRequest.mockResolvedValue(
      undefined
    );

    await expect(
      createSportsLiveSession("sports-event-001")
    ).rejects.toThrow(
      "Sports live session did not return a valid TTL."
    );

    expect(
      mocks.authenticatedAtlasApiRequest
    ).toHaveBeenCalledWith(
      "/sports/live/sessions/live-session-invalid-ttl",
      expect.objectContaining({
        method: "DELETE",
        cache: "no-store"
      })
    );
  });

  it("releases an admitted Sports live lease when playback validation fails", async () => {
    mocks.authenticatedAtlasApiRequestWithMetadata.mockResolvedValue({
      data: {
        available: true,
        action: "watch_now",
        label: "Watch Now",
        backend: "jellyfin",
        source_type: "library",
        provider: "jellyfin",
        requested_target_id: "jf-channel-exact",
        playable_target_id: "jf-channel-exact",
        title: "Atlas Test Channel",
        media_type: "video",
        duration_ticks: null,
        can_seek: false,
        playback_bootstrap_url:
          "https://playback.shadowinc.co/_atlas/playback/bootstrap",
        playback_capability: "sports-capability-invalid-body",
        audio_tracks: [],
        subtitle_tracks: [],
        previous_target_id: null,
        next_target_id: null
      },
      status: 200,
      requestId: "sports-live-invalid-body",
      headers: new Headers({
        "X-Atlas-Live-Session-ID": "live-session-invalid-body",
        "X-Atlas-Live-Session-TTL": "90"
      })
    });

    mocks.authenticatedAtlasApiRequest.mockResolvedValue(
      undefined
    );

    await expect(
      createSportsLiveSession("sports-event-001")
    ).rejects.toThrow(
      "Sports live playback response was not a live session."
    );

    expect(
      mocks.authenticatedAtlasApiRequest
    ).toHaveBeenCalledWith(
      "/sports/live/sessions/live-session-invalid-body",
      expect.objectContaining({
        method: "DELETE",
        cache: "no-store"
      })
    );
  });

  it("heartbeats an authenticated Sports live session lease", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      session_id: "live-session-001",
      ttl_seconds: 90
    });

    const result = await heartbeatSportsLiveSession(
      "live-session-001"
    );

    expect(
      mocks.authenticatedAtlasApiRequest
    ).toHaveBeenCalledWith(
      "/sports/live/sessions/live-session-001/heartbeat",
      expect.objectContaining({
        method: "POST",
        cache: "no-store"
      })
    );

    expect(result).toEqual({
      liveSessionId: "live-session-001",
      ttlSeconds: 90
    });
  });

  it("releases an authenticated Sports live session lease", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue(
      undefined
    );

    await expect(
      releaseSportsLiveSession(
        "live-session-001"
      )
    ).resolves.toBeUndefined();

    expect(
      mocks.authenticatedAtlasApiRequest
    ).toHaveBeenCalledWith(
      "/sports/live/sessions/live-session-001",
      expect.objectContaining({
        method: "DELETE",
        cache: "no-store"
      })
    );
  });

  it("requests only provider identity from the browser", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      subscription_id: "sub-atlas-001",
      type: "event",
      provider: "thesportsdb",
      provider_event_id: "event-001",
      name: "Atlas United vs Atlas City",
      user_id: "usr-atlas-001",
      enabled: true,
      created_at: "2026-08-16T20:00:00Z"
    });

    const subscription = await requestSportsEvent({
      provider: "thesportsdb",
      providerEventId: "event-001"
    });

    expect(mocks.authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/subscriptions",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        body: {
          provider: "thesportsdb",
          provider_event_id: "event-001"
        },
        retryPolicy: expect.objectContaining({
          maxRetries: 0
        })
      })
    );

    expect(subscription.userId).toBe("usr-atlas-001");

    expect(subscription.providerEventId).toBe("event-001");
  });

  it("does not expose server-owned identity in request input", () => {
    const input = {
      provider: "thesportsdb",
      providerEventId: "event-001"
    };

    expect(input).not.toHaveProperty("userId");
    expect(input).not.toHaveProperty("subscriptionId");
    expect(input).not.toHaveProperty("name");
    expect(input).not.toHaveProperty("type");
  });
  it("searches upcoming Sports events through the event contract", async () => {
    mocks.authenticatedAtlasApiRequest.mockResolvedValue({
      events: [
        {
          provider: "thesportsdb",
          provider_event_id: "event-090",
          name: "Detroit Lions vs New Orleans Saints",
          sport: "American Football",
          league: "NFL",
          start_at: "2026-09-06T17:00:00Z",
          status: "scheduled",
          requested: false
        }
      ]
    });

    const results = await searchSports("event", "Lions");

    expect(mocks.authenticatedAtlasApiRequest).toHaveBeenCalledWith(
      "/sports/search/events?provider=thesportsdb&query=Lions",
      expect.objectContaining({ method: "GET", cache: "no-store" })
    );
    expect(results[0]).toMatchObject({
      kind: "event",
      id: "event-090",
      name: "Detroit Lions vs New Orleans Saints",
      status: "scheduled",
      requested: false
    });
  });
});
