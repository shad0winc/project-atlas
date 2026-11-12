import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { SportsCurrentlyLive } from "./SportsCurrentlyLive";
import { SportsRequestView } from "./SportsRequestView";
const props = {
  follows: [], searchResults: [], searchType: "league" as const,
  onSearch: vi.fn(), onFollow: vi.fn(), onUnfollow: vi.fn(), onBrowse: vi.fn(),
  onRequestEvent: vi.fn(), onSetRecording: vi.fn(), onViewAllUpcoming: vi.fn(),
};
describe("upcoming selection presentation", () => {
  it("labels the single selection and offers all followed upcoming", () => {
    const html = renderToStaticMarkup(<SportsRequestView {...props} events={[]} upcomingScopeLabel="NBA" allFollowedSelected={false} />);
    expect(html).toContain("NBA"); expect(html).toContain("View all followed upcoming");
    expect(html).toContain('aria-pressed="false"');
  });
  it("shows a selected team's live game beside the upcoming schedule", () => {
    const html = renderToStaticMarkup(<SportsRequestView
      {...props}
      events={[]}
      upcomingScopeLabel="Boston Celtics"
      allFollowedSelected={false}
      selectedLiveEvents={<SportsCurrentlyLive
        events={[{
          provider: "espn", providerEventId: "basketball-nba-fixture",
          name: "Boston Celtics at Toronto Raptors", sport: "Basketball", league: "NBA",
          startAt: "2026-11-12T00:00:00Z", status: "live", requested: false,
        }]}
        availability={{}}
        unavailable={false}
        scopeLabel="Boston Celtics"
        onWatchLive={vi.fn()}
      />}
    />);
    expect(html).toContain("Boston Celtics at Toronto Raptors");
    expect(html).toContain("Provider-reported live events for Boston Celtics.");
    expect(html.indexOf("Next 7 days")).toBeLessThan(html.indexOf("Boston Celtics at Toronto Raptors"));
    expect(html).toContain("Live playback is not currently available.");
    expect(html).not.toContain("Watch Live");
  });

  it("shows retained games during a failed refresh with an explicit last load", () => {
    const html = renderToStaticMarkup(<SportsRequestView {...props} scheduleUnavailable scheduleRefreshing scheduleLoadedAt={1793448000000} events={[{
      provider: "thesportsdb", providerEventId: "fixture", name: "Retained fixture", sport: "Basketball", league: "NBA",
      startAt: "2026-11-01T20:00:00Z", status: "scheduled", requested: false,
    }]} />);
    expect(html).toContain("Retained fixture"); expect(html).toContain("previously loaded upcoming events");
    expect(html).toContain("Last successful load:"); expect(html).toContain("Updating upcoming events");
    expect(html).not.toContain("No upcoming Sports events to show");
  });
});
