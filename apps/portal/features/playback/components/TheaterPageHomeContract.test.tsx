import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { TheaterPageClient } from "../../../app/(protected)/portal/theater/TheaterPageClient";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams()
}));

vi.mock("../../../components/portal/PortalPage", () => ({
  PortalPage: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

vi.mock("../../../features/media", () => ({
  MediaCatalogView: () => <div>theater-catalog</div>
}));

describe("TheaterPageClient home", () => {
  it("renders a playback hub when there is no exact target", () => {
    const markup = renderToStaticMarkup(<TheaterPageClient />);

    expect(markup).toContain("Playback hub");
    expect(markup).toContain("Available to watch");
    expect(markup).toContain("theater-catalog");
    expect(markup).not.toContain("Playback unavailable");
  });
});
