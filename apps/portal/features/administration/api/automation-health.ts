import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type AutomationHealth = Readonly<{
  observed_at: string;
  api_configuration: Readonly<{
    receipt_recovery: "enabled" | "disabled" | "invalid";
    acquisition_routing: "enabled" | "disabled" | "invalid";
  }>;
  request_registry: Readonly<{
    status: "observed" | "unavailable";
    schema_version?: number;
    request_count?: number;
    unresolved_submission_count?: number;
    observed_receipt_count?: number;
    pending_event_count?: number;
  }>;
  request_reconciliation: Readonly<{
    status: "healthy" | "attention" | "stale" | "unavailable";
    last_success?: string;
    consecutive_failures?: number;
  }>;
}>;

export async function loadAutomationHealth(signal?: AbortSignal): Promise<AutomationHealth> {
  const response = await authenticatedAtlasApiRequest<{
    schema_version: number; api_version: string; success: boolean;
    generated_at: string; data: AutomationHealth;
  }>("/admin/automation-health", {
    method: "GET", cache: "no-store", signal
  });
  const flags = ["enabled", "disabled", "invalid"];
  const timestamp = (value: unknown) => typeof value === "string" && Number.isFinite(Date.parse(value));
  const count = (value: unknown) => typeof value === "number" && Number.isSafeInteger(value) && value >= 0;
  if (!response || response.schema_version !== 1 || response.api_version !== "v1" ||
      response.success !== true || !timestamp(response.generated_at)) {
    throw new Error("Automation health response is unavailable.");
  }
  const report = response.data;
  if (!report || !timestamp(report.observed_at) ||
      !flags.includes(report.api_configuration?.receipt_recovery) ||
      !flags.includes(report.api_configuration?.acquisition_routing) ||
      !["observed", "unavailable"].includes(report.request_registry?.status) ||
      !["healthy", "attention", "stale", "unavailable"].includes(report.request_reconciliation?.status)) {
    throw new Error("Automation health response is unavailable.");
  }
  const registry = report.request_registry;
  if (registry.status === "observed" && (
      ![1, 2].includes(registry.schema_version ?? 0) || !count(registry.request_count) ||
      (registry.schema_version === 2 && (!count(registry.unresolved_submission_count) ||
        !count(registry.observed_receipt_count) || !count(registry.pending_event_count))))) {
    throw new Error("Automation health response is unavailable.");
  }
  const task = report.request_reconciliation;
  if (task.status !== "unavailable" && (!timestamp(task.last_success) || !count(task.consecutive_failures))) {
    throw new Error("Automation health response is unavailable.");
  }
  return report;
}
