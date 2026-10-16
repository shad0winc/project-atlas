// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SportsRequestView, type SportsRequestViewProps } from "./SportsRequestView";

let root: Root;
let container: HTMLDivElement;
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
const saved = {
  subscriptionId: "primary-league", type: "league" as const,
  provider: "thesportsdb", providerId: "same-id", name: "Primary league",
  userId: "owner", enabled: true, record: false, createdAt: null,
};
const result = {
  kind: "league" as const, provider: "espn", id: "same-id",
  name: "Secondary league", sport: "Football", league: "NFL",
};
function props(): SportsRequestViewProps {
  return {
    events: [], follows: [], searchResults: [result], searchType: "league",
    onSearch: vi.fn(async () => {}), onFollow: vi.fn(async () => {}),
    onUnfollow: vi.fn(async () => {}), onBrowse: vi.fn(async () => {}),
    onSetRecording: vi.fn(async () => {}),
    onRequestEvent: vi.fn(),
  };
}
async function mount(value: SportsRequestViewProps) {
  await act(async () => root.render(<SportsRequestView {...value} />));
}
function discovery() {
  return container.querySelector('[aria-label="Sports league search results"]')!;
}
async function click(scope: Element, label: string) {
  const button = [...scope.querySelectorAll("button")]
    .find((item) => item.textContent === label);
  expect(button).toBeDefined();
  await act(async () => button!.click());
}

describe("provider-scoped Sports discovery actions", () => {
  it("does not mistake a different provider's same ID for an existing follow", async () => {
    const value = { ...props(), follows: [saved] };
    await mount(value);
    expect(discovery().textContent).not.toContain("Unfollow");
    await click(discovery(), "Follow");
    expect(value.onFollow).toHaveBeenCalledWith("league", "same-id", "espn");
    expect(value.onUnfollow).not.toHaveBeenCalled();
  });

  it("passes the search result provider to View upcoming", async () => {
    const value = props();
    await mount(value);
    await click(discovery(), "View upcoming");
    expect(value.onBrowse).toHaveBeenCalledWith("league", "same-id", "espn");
  });

  it("passes the saved follow provider to View upcoming", async () => {
    const value = { ...props(), searchResults: [], follows: [{ ...saved, provider: "espn" }] };
    await mount(value);
    await click(container, "View upcoming");
    expect(value.onBrowse).toHaveBeenCalledWith("league", "same-id", "espn");
  });

  it("unfollows the matching provider when IDs overlap", async () => {
    const secondary = { ...saved, provider: "espn", subscriptionId: "secondary-league" };
    const value = { ...props(), follows: [saved, secondary] };
    await mount(value);
    await click(discovery(), "Unfollow");
    expect(value.onUnfollow).toHaveBeenCalledWith("secondary-league");
    expect(value.onFollow).not.toHaveBeenCalled();
  });

  it("retains SportsDB behavior for legacy results without provider metadata", async () => {
    const legacy = {
      kind: result.kind, id: result.id, name: result.name,
      sport: result.sport, league: result.league,
    };
    const value = { ...props(), searchResults: [legacy] };
    await mount(value);
    await click(discovery(), "Follow");
    expect(value.onFollow).toHaveBeenCalledWith("league", "same-id", "thesportsdb");
  });
});
