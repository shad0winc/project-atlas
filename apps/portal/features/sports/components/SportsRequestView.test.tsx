import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { SportsRequestView } from "./SportsRequestView";

const baseProps = {
  follows: [],
  searchResults: [],
  searchType: "team" as const,
  onSearch: vi.fn(),
  onFollow: vi.fn(),
  onUnfollow: vi.fn(),
  onSetRecording: vi.fn(),
  onBrowse: vi.fn(),
  onRequestEvent: vi.fn()
};

describe("SportsRequestView", () => {
  it("renders discovery, following, and upcoming event surfaces", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        {...baseProps}
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
      />
    );

    expect(markup).toContain("Find your Sports");
    expect(markup).toContain("My Sports");
    expect(markup).toContain("Atlas United vs Atlas City");
    expect(markup).toContain("Request event");
    expect(markup).toContain("does not automatically record events");
  });

  it("renders team search results with follow and browse controls", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        {...baseProps}
        events={[]}
        searchResults={[
          {
            kind: "team",
            id: "team-001",
            name: "Atlas United",
            sport: "Soccer",
            league: "Atlas Test League"
          }
        ]}
      />
    );

    expect(markup).toContain("Atlas United");
    expect(markup).toContain("Follow");
    expect(markup).toContain("View upcoming");
  });

  it("renders followed Sports with an unfollow control", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        {...baseProps}
        events={[]}
        follows={[
          {
            subscriptionId: "sub-001",
            type: "team",
            provider: "thesportsdb",
            providerId: "team-001",
            name: "Atlas United",
            userId: "usr-001",
            enabled: true,
            record: false,
            createdAt: "2026-08-30T20:00:00.000Z"
          }
        ]}
      />
    );

    expect(markup).toContain("Following");
    expect(markup).toContain("Unfollow");
    expect(markup).toContain("View upcoming");
  });

  it("renders recording controls for followed events", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        {...baseProps}
        events={[]}
        follows={[
          {
            subscriptionId: "sub-event-001",
            type: "event",
            provider: "thesportsdb",
            providerId: "event-001",
            name: "Atlas United vs Atlas City",
            userId: "usr-001",
            enabled: true,
            record: false,
            createdAt: "2026-08-30T20:00:00.000Z"
          },
          {
            subscriptionId: "sub-event-002",
            type: "event",
            provider: "thesportsdb",
            providerId: "event-002",
            name: "Atlas Rovers vs Atlas County",
            userId: "usr-001",
            enabled: true,
            record: true,
            createdAt: "2026-08-30T20:00:00.000Z"
          }
        ]}
      />
    );

    expect(markup).toContain("Atlas United vs Atlas City");
    expect(markup).toContain("Record event");
    expect(markup).toContain("Cancel recording");
    expect(markup).toContain("Unfollow");
  });

  it("preserves requested event identity and disabled state", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        {...baseProps}
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
      />
    );

    expect(markup).toContain("Requested");
    expect(markup).toContain('data-provider="thesportsdb"');
    expect(markup).toContain('data-provider-event-id="event-001"');
    expect(markup).toMatch(/<button[^>]*disabled/);
  });

  it("renders event search results with request and recording controls", () => {
    const markup = renderToStaticMarkup(
      <SportsRequestView
        {...baseProps}
        events={[]}
        searchType="event"
        searchResults={[
          {
            kind: "event",
            id: "event-090",
            provider: "thesportsdb",
            name: "Detroit Lions vs New Orleans Saints",
            sport: "American Football",
            league: "NFL",
            startAt: "2026-09-06T17:00:00.000Z",
            status: "scheduled",
            requested: false
          }
        ]}
      />
    );

    expect(markup).toContain("Detroit Lions vs New Orleans Saints");
    expect(markup).toContain("Request event");
    expect(markup).toContain("Record event");
    expect(markup).not.toContain("View upcoming");
  });

});
