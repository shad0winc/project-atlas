// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { loadServiceLifecycleOverview, loadServiceUpdateReport } from "../api/services";
import { createServiceLifecycleSnapshot } from "../types/services";
import { ServiceView } from "./ServiceView";

vi.mock("../../../lib/auth/use-auth", () => ({ useAuth: () => ({ isAuthenticated: true }) }));
vi.mock("../api/services", () => ({
  loadManagedServiceDetail: vi.fn(),
  loadServiceLifecycleOverview: vi.fn(),
  loadServiceUpdateReport: vi.fn()
}));

const snapshot = createServiceLifecycleSnapshot({
  services: [],
  health: {},
  summary: {},
  updates: { counts: { "update-available": 8 } },
  history: {}
});

describe("Check for updates", () => {
  const container = document.createElement("div");
  let root: ReturnType<typeof createRoot>;

  beforeEach(async () => {
    vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
    root = createRoot(container);
    vi.mocked(loadServiceLifecycleOverview).mockResolvedValue(snapshot);
    await act(async () => root.render(<ServiceView />));
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    vi.unstubAllGlobals();
  });

  it("keeps the overview mounted and confirms a check even when the count is unchanged", async () => {
    let finish!: (report: typeof snapshot.updates) => void;
    vi.mocked(loadServiceUpdateReport).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    );

    const button = container.querySelector("button")!;
    await act(async () => button.click());

    expect(button.disabled).toBe(true);
    expect(button.textContent).toContain("Checking for updates");
    expect(container.textContent).toContain("8 updates available");

    await act(async () => finish(snapshot.updates));

    expect(container.querySelector("button")).toBe(button);
    expect(button.disabled).toBe(false);
    expect(container.querySelector('[role="status"]')?.textContent).toBe("Update check complete.");
    expect(loadServiceUpdateReport).toHaveBeenCalledTimes(1);
    expect(loadServiceLifecycleOverview).toHaveBeenCalledTimes(1);
  });

  it("keeps the last report visible if a check fails and allows retry", async () => {
    vi.mocked(loadServiceUpdateReport).mockRejectedValueOnce(new Error("Service unavailable"));
    const button = container.querySelector("button")!;

    await act(async () => button.click());

    expect(container.textContent).toContain("8 updates available");
    expect(container.querySelector('[role="status"]')?.textContent).toContain(
      "Showing the previous results."
    );
    expect(button.disabled).toBe(false);

    vi.mocked(loadServiceUpdateReport).mockResolvedValueOnce({
      ...snapshot.updates,
      updateAvailable: 3
    });
    await act(async () => button.click());
    expect(container.textContent).toContain("3 updates available");
    expect(container.querySelector('[role="status"]')?.textContent).toBe("Update check complete.");
  });
});
