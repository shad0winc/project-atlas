// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";

import { loadBazarrUpdatePlan } from "../api/services";
import { BazarrUpdatePreview } from "./BazarrUpdatePreview";

vi.mock("../api/services", () => ({ loadBazarrUpdatePlan: vi.fn() }));

it("loads the Bazarr dry-run plan on demand and displays both pinned images", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const container = document.createElement("div");
  const root = createRoot(container);
  try {
    const repository = "lscr.io/linuxserver/bazarr";
    const current = `${repository}@sha256:${"a".repeat(64)}`;
    const target = `${repository}@sha256:${"b".repeat(64)}`;
    vi.mocked(loadBazarrUpdatePlan).mockResolvedValueOnce({
      current_image: { canonical_reference: current },
      target_image: { canonical_reference: target },
      warnings: ["Back up the Bazarr database."]
    });

    await act(async () => root.render(<BazarrUpdatePreview />));
    expect(loadBazarrUpdatePlan).not.toHaveBeenCalled();
    await act(async () => container.querySelector("button")!.click());
    expect(loadBazarrUpdatePlan).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Dry-run update plan");
    expect(container.textContent).toContain(current);
    expect(container.textContent).toContain(target);
    expect(container.textContent).toContain("Back up the Bazarr database.");
  } finally {
    await act(async () => root.unmount());
    vi.unstubAllGlobals();
  }
});
