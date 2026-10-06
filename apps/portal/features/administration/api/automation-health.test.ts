import { describe, expect, it, vi } from "vitest";
const request = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/services/authenticated", () => ({ authenticatedAtlasApiRequest: request }));
import { loadAutomationHealth } from "./automation-health";

function envelope(data: unknown) {
  return { schema_version: 1, api_version: "v1", success: true,
    generated_at: "2026-10-06T21:43:17.519175Z", data };
}

describe("automation health transport", () => {
  it("uses an authenticated no-store GET and preserves cancellation", async () => {
    const report = { observed_at: "2026-10-06T20:00:00Z",
      api_configuration: { receipt_recovery: "enabled", acquisition_routing: "disabled" },
      request_registry: { status: "unavailable" }, request_reconciliation: { status: "unavailable" } };
    request.mockResolvedValue(envelope(report));
    const controller = new AbortController();
    expect(await loadAutomationHealth(controller.signal)).toEqual(report);
    expect(request).toHaveBeenCalledWith("/admin/automation-health", {
      method: "GET", cache: "no-store", signal: controller.signal
    });
  });
  it("rejects incomplete observations rather than inventing zero counts", async () => {
    request.mockResolvedValue(envelope({ observed_at: "2026-10-06T20:00:00Z",
      api_configuration: { receipt_recovery: "enabled", acquisition_routing: "disabled" },
      request_registry: { status: "observed", schema_version: 2, request_count: 8 },
      request_reconciliation: { status: "unavailable" } }));
    await expect(loadAutomationHealth()).rejects.toThrow("Automation health response is unavailable.");
  });
  it("unwraps a healthy schema2 response matching the deployed API", async () => {
    const report = { observed_at: "2026-10-06T21:43:17.518851+00:00",
      api_configuration: { receipt_recovery: "enabled", acquisition_routing: "disabled" },
      request_registry: { status: "observed", schema_version: 2, request_count: 8,
        unresolved_submission_count: 0, observed_receipt_count: 0, pending_event_count: 0 },
      request_reconciliation: { status: "healthy", task_status: "healthy",
        last_success: "2026-10-06T21:43:00.202066+00:00", consecutive_failures: 0,
        snapshot_age_seconds: 16, success_age_seconds: 17 } };
    request.mockResolvedValue(envelope(report));
    expect(await loadAutomationHealth()).toEqual(report);
  });
  it.each([
    { success: false }, { schema_version: 2 }, { api_version: "v2" },
    { generated_at: "invalid" }, { data: null },
  ])("rejects an invalid success envelope %j", async (invalid) => {
    request.mockResolvedValue({ ...envelope({}), ...invalid });
    await expect(loadAutomationHealth()).rejects.toThrow("Automation health response is unavailable.");
  });

});
