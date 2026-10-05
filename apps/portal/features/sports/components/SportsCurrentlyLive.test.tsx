import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { SportsCurrentlyLive } from "./SportsCurrentlyLive";
import { followedLiveEvents } from "../services/currentlyLive";
import type { SportsEvent, SportsFollow } from "../types/sports";
const event: SportsEvent = {
  provider: "thesportsdb",
  providerEventId: "game",
  name: "Panthers vs Lions",
  league: "NFL",
  sport: "Football",
  status: "live",
  startAt: "2026-10-05T00:20:00Z",
  requested: false,
};
const saved: SportsFollow = {
  type: "event",
  provider: "thesportsdb",
  providerId: "game",
  name: event.name,
  subscriptionId: "sub",
  userId: "owner",
  enabled: true,
  record: false,
  createdAt: null,
};
describe("Currently Live cards", () => {
  it("shows start date and timezone but requires authoritative availability to watch", () => {
    const render = (available: boolean) =>
      renderToStaticMarkup(
        <SportsCurrentlyLive
          events={[event]}
          availability={{
            "thesportsdb:game": {
              available,
              atlasChannelId: "sports-live-game",
            },
          }}
          unavailable={false}
          onWatchLive={vi.fn()}
        />,
      );
    expect(render(true)).toContain("Watch Live");
    expect(render(true)).toContain('dateTime="2026-10-05T00:20:00Z"');
    expect(render(true)).toContain("2026");
    expect(render(false)).not.toContain("Watch Live");
  });
  it("removes an event when its next successful snapshot reports final", () => {
    const events = followedLiveEvents(
      [{ ...event, status: "final" }],
      [saved],
      Date.parse("2026-10-05T01:00:00Z"),
    );
    const markup = renderToStaticMarkup(
      <SportsCurrentlyLive
        events={events}
        availability={{}}
        unavailable={false}
        onWatchLive={vi.fn()}
      />,
    );
    expect(markup).not.toContain(event.name);
    expect(markup).toContain("No followed events");
  });
  it("reports metadata failure without retaining stale live claims", () => {
    const markup = renderToStaticMarkup(
      <SportsCurrentlyLive
        events={[]}
        availability={{}}
        unavailable={true}
        onWatchLive={vi.fn()}
      />,
    );
    expect(markup).toContain("temporarily unavailable");
    expect(markup).not.toContain("Watch Live");
  });
});
