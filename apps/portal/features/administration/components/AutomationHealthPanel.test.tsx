import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AutomationHealthState } from "../hooks/use-automation-health";

const mocked = vi.hoisted(() => ({
  allowed: true,
  state: { status: "loading" } as AutomationHealthState,
  enabled: vi.fn()
}));
vi.mock("../../../lib/authorization", () => ({
  ATLAS_PERMISSIONS: { systemHealthRead: "system.health.read" },
  usePermission: () => ({ can: () => mocked.allowed })
}));
vi.mock("../hooks/use-automation-health", () => ({
  useAutomationHealth: (enabled: boolean) => {
    mocked.enabled(enabled);
    return { state: mocked.state, refresh: vi.fn() };
  }
}));
import { AutomationHealthPanel } from "./AutomationHealthPanel";

describe("AutomationHealthPanel", () => {
  beforeEach(() => { mocked.allowed = true; mocked.state = { status: "loading" }; mocked.enabled.mockClear(); });
  it("hides health and disables its reader without permission", () => {
    mocked.allowed = false;
    expect(renderToStaticMarkup(<AutomationHealthPanel />)).toBe("");
    expect(mocked.enabled).toHaveBeenCalledWith(false);
  });
  it("renders loading and a sanitized error without success claims", () => {
    expect(renderToStaticMarkup(<AutomationHealthPanel />)).toContain("Loading automation health");
    mocked.state = { status: "error" };
    const html = renderToStaticMarkup(<AutomationHealthPanel />);
    expect(html).toContain("Automation health is unavailable");
    expect(html).not.toContain("Status: healthy");
  });
  it("distinguishes enabled flags, unresolved work and stale scheduler observations", () => {
    mocked.state = { status: "ready", report: {
      observed_at: "2026-10-06T20:00:00Z",
      api_configuration: { receipt_recovery: "enabled", acquisition_routing: "disabled" },
      request_registry: { status: "observed", schema_version: 2, request_count: 8,
        unresolved_submission_count: 2, observed_receipt_count: 1, pending_event_count: 0 },
      request_reconciliation: { status: "stale", last_success: "2026-10-06T19:00:00Z", consecutive_failures: 0 }
    }};
    const html = renderToStaticMarkup(<AutomationHealthPanel />);
    expect(html).toContain("Receipt recovery: enabled");
    expect(html).toContain("Acquisition routing: disabled");
    expect(html).toContain("Unresolved submissions: 2");
    expect(html).toContain("Status: stale");
    expect(html).toContain("does not establish successful receipt recovery");
    expect(html).not.toMatch(/>Reset|>Retry submission|>Clear journal/);
  });
});
