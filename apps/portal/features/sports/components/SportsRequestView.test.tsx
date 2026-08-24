import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { SportsRequestView } from "./SportsRequestView";

describe("SportsRequestView", () => {
  it("renders the smallest v1 Sports request surface", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        events={[
          {
            provider: "thesportsdb",
            providerEventId: "event-001",
            name: "Atlas United vs Atlas City",
            sport: "Soccer",
            league: "Atlas Test League",
            startAt: "2026-08-17T20:00:00.000Z",
            status: "scheduled",
            requested: false
          }
        ]}
        onRequestEvent={vi.fn()}
      />
    );

    expect(markup).toContain("Sports");
    expect(markup).toContain("Atlas United vs Atlas City");
    expect(markup).toContain("Atlas Test League");
    expect(markup).toContain("Request event");
  });

  it("renders an already-requested event as disabled", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        events={[
          {
            provider: "thesportsdb",
            providerEventId: "event-001",
            name: "Atlas United vs Atlas City",
            sport: "Soccer",
            league: "Atlas Test League",
            startAt: "2026-08-17T20:00:00.000Z",
            status: "scheduled",
            requested: true
          }
        ]}
        onRequestEvent={vi.fn()}
      />
    );

    expect(markup).toContain("Requested");
    expect(markup).toMatch(/<button[^>]*disabled/);
  });

  it("preserves provider event identity on the request control", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        events={[
          {
            provider: "thesportsdb",
            providerEventId: "event-001",
            name: "Atlas United vs Atlas City",
            sport: "Soccer",
            league: "Atlas Test League",
            startAt: "2026-08-17T20:00:00.000Z",
            status: "scheduled",
            requested: false
          }
        ]}
        onRequestEvent={vi.fn()}
      />
    );

    expect(markup).toContain('data-provider="thesportsdb"');

    expect(markup).toContain('data-provider-event-id="event-001"');
  });
});
