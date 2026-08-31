import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { LibraryPageClient } from "../../../app/(protected)/portal/library/LibraryPageClient";

vi.mock("../../../lib/authorization", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/authorization")>(
    "../../../lib/authorization"
  );

  return {
    ...actual,
    usePermission: () => ({
      can: (permission: string) => permission === "requests.read"
    })
  };
});

vi.mock("../../../components/portal/PortalPage", () => ({
  PortalPage: ({ children }: { children: React.ReactNode }) => <>{children}</>
}));

vi.mock("../../../features/media", () => ({
  MediaCatalogView: () => <div>catalog-surface</div>
}));

vi.mock("../../../features/requests", () => ({
  RequestsView: () => <div>request-lifecycle-surface</div>
}));

describe("LibraryPageClient", () => {
  it("composes available media and request lifecycle surfaces", () => {
    const markup = renderToStaticMarkup(<LibraryPageClient />);

    expect(markup).toContain("catalog-surface");
    expect(markup).toContain("request-lifecycle-surface");
    expect(markup).toContain("Request status");
  });
});
