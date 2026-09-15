import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";

describe("Sports page UX coordination", () => {
  const source = readFileSync(
    new URL("../../../app/(protected)/portal/sports/SportsPageClient.tsx", import.meta.url),
    "utf8"
  );

  it("removes a successfully followed result from Discover", () => {
    expect(source).toContain(
      "current.filter((item) => item.id !== providerId)"
    );
  });

  it("adds a requested event to local follow state without a reload", () => {
    expect(source).toContain(
      "providerId: subscription.providerEventId"
    );
    expect(source).toContain(
      "subscriptionId: subscription.subscriptionId"
    );
    expect(source).toContain(
      "record: false"
    );
  });

  it("wires authoritative live availability for followed events", () => {
    expect(source).toContain("loadSportsLiveAvailability");

    expect(source).toContain(
      'follow.type === "event"'
    );

    expect(source).toContain(
      "liveAvailabilityByEvent={liveAvailabilityByEvent}"
    );
  });

  it("owns the authenticated Watch Live player lease lifecycle", () => {
    expect(source).toContain(
      "createSportsLiveSession"
    );

    expect(source).toContain(
      "heartbeatSportsLiveSession"
    );

    expect(source).toContain(
      "releaseSportsLiveSession"
    );

    expect(source).toContain(
      "AtlasTheaterPlayer"
    );

    expect(source).toContain(
      "handleWatchLive"
    );

    expect(source).toContain(
      "onWatchLive={handleWatchLive}"
    );

    expect(source).toContain(
      "resolveSportsLiveSession"
    );

    expect(source).toContain(
      "sessionResolver={resolveSportsLiveSession}"
    );

    expect(source).toContain(
      "ttlSeconds * 1000"
    );

    expect(source).toContain(
      "/ 2"
    );

    expect(source).toContain(
      "heartbeatSportsLiveSession("
    );

    expect(source).toContain(
      "releaseSportsLiveSession("
    );

    expect(source).toContain(
      "Close live playback"
    );
  });

  it("scrolls to Upcoming Events after browse succeeds", () => {
    expect(source).toContain(
      'getElementById("sports-upcoming-events")'
    );
    expect(source).toContain(
      'scrollIntoView({ behavior: "smooth", block: "start" })'
    );
  });
});
