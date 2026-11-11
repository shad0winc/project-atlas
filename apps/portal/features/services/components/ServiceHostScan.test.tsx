// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { expect, it, vi } from "vitest";

import { loadServiceLifecycleOverview, loadServiceUpdateReport, scanServiceUpdates } from "../api/services";
import { createServiceLifecycleSnapshot } from "../types/services";
import { ServiceView } from "./ServiceView";

vi.mock("../../../lib/auth/use-auth", () => ({
  useAuth: () => ({ isAuthenticated: true, user: { roles: ["global_admin"] } })
}));
vi.mock("../api/services", () => ({
  loadManagedServiceDetail: vi.fn(),
  loadServiceLifecycleOverview: vi.fn(),
  loadServiceUpdateReport: vi.fn(),
  scanServiceUpdates: vi.fn()
}));

it("waits for an admin host scan before replacing the visible observations", async () => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  const container = document.createElement("div");
  const root = createRoot(container);
  const previous = createServiceLifecycleSnapshot({
    services: [], health: {}, summary: {}, updates: { counts: { "update-available": 8 } }, history: {}
  });
  const current = createServiceLifecycleSnapshot({
    services: [], health: {}, summary: {}, updates: { counts: { "update-available": 0 } }, history: {}
  });
  let finish!: () => void;
  vi.mocked(loadServiceLifecycleOverview).mockResolvedValueOnce(previous).mockResolvedValueOnce(current);
  vi.mocked(scanServiceUpdates).mockImplementationOnce(() => new Promise<void>((resolve) => { finish = resolve; }));
  try {
    await act(async () => root.render(<ServiceView />));
    const button = container.querySelector("button")!;
    await act(async () => button.click());
    expect(scanServiceUpdates).toHaveBeenCalledTimes(1);
    expect(loadServiceLifecycleOverview).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("8 updates available");
    await act(async () => finish());
    expect(loadServiceLifecycleOverview).toHaveBeenCalledTimes(2);
    expect(loadServiceUpdateReport).not.toHaveBeenCalled();
    expect(container.querySelector("button")).toBe(button);
    expect(container.textContent).toContain("0 updates available");
  } finally {
    await act(async () => root.unmount());
    vi.unstubAllGlobals();
  }
});
