import { describe, expect, it, vi } from "vitest";
const request = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/services/authenticated", () => ({ authenticatedAtlasApiRequest: request }));
import { loadAutomationHealth } from "./automation-health";

describe("automation health transport", () => {
  it("uses an authenticated no-store GET and preserves cancellation", async () => {
    const report = { observed_at: "2026-10-06T20:00:00Z",
      api_configuration: { receipt_recovery: "enabled", acquisition_routing: "disabled" },
      request_registry: { status: "unavailable" }, request_reconciliation: { status: "unavailable" } };
    request.mockResolvedValue(report);
    const controller = new AbortController();
    expect(await loadAutomationHealth(controller.signal)).toEqual(report);
    expect(request).toHaveBeenCalledWith("/admin/automation-health", {
      method: "GET", cache: "no-store", signal: controller.signal
    });
  });
  it("rejects incomplete observations rather than inventing zero counts", async () => {
    request.mockResolvedValue({ observed_at: "2026-10-06T20:00:00Z",
      api_configuration: { receipt_recovery: "enabled", acquisition_routing: "disabled" },
      request_registry: { status: "observed", schema_version: 2, request_count: 8 },
      request_reconciliation: { status: "unavailable" } });
    await expect(loadAutomationHealth()).rejects.toThrow("Automation health response is unavailable.");
  });
});
