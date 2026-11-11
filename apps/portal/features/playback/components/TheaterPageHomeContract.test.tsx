import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { TheaterPageClient } from "../../../app/(protected)/portal/theater/TheaterPageClient";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams()
}));

vi.mock("../../../components/portal/PortalPage", () => ({
  PortalPage: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

describe("TheaterPageClient without a target", () => {
  it("links to the Media Library for selection", () => {
    const markup = renderToStaticMarkup(<TheaterPageClient />);

    expect(markup).toContain('href="/portal/media?view=library"');
    expect(markup).toContain("Choose a title in Library");
    expect(markup).not.toContain("Playback unavailable");
  });
});
