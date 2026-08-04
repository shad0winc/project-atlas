import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { PortalSchedulerSnapshot } from "../types/scheduler";

import { SchedulerFailuresPanel } from "./SchedulerFailuresPanel";

function scheduler(overrides: Partial<PortalSchedulerSnapshot> = {}): PortalSchedulerSnapshot {
  return {
    status: "available",
    detail: null,
    registeredCount: 4,
    enabledCount: 4,
    disabledCount: 0,
    dueCount: 1,
    runningCount: 0,
    failedCount: 0,
    lastRunAt: "2026-08-04T14:00:00.000Z",
    nextRunAt: "2026-08-04T15:00:00.000Z",
    recentFailures: [],
    ...overrides
  };
}

describe("SchedulerFailuresPanel", () => {
  it("renders a clear state when no failures exist", () => {
    const markup = renderToStaticMarkup(<SchedulerFailuresPanel scheduler={scheduler()} />);

    expect(markup).toContain("Recent scheduler failures");
    expect(markup).toContain("Clear");
    expect(markup).toContain("Atlas has no recent scheduler task failures.");
  });

  it("renders one failure with its task, error, and timestamp", () => {
    const markup = renderToStaticMarkup(
      <SchedulerFailuresPanel
        scheduler={scheduler({
          failedCount: 1,
          recentFailures: [
            {
              taskName: "backup.verify",
              failedAt: "2026-08-04T13:30:00.000Z",
              error: "Backup verification failed."
            }
          ]
        })}
      />
    );

    expect(markup).toContain("1 failure");
    expect(markup).not.toContain("1 failures");
    expect(markup).toContain("backup.verify");
    expect(markup).toContain("Backup verification failed.");
    expect(markup).toContain("Failed");
    expect(markup).toContain('dateTime="2026-08-04T13:30:00.000Z"');
  });

  it("renders multiple failures", () => {
    const markup = renderToStaticMarkup(
      <SchedulerFailuresPanel
        scheduler={scheduler({
          failedCount: 2,
          recentFailures: [
            {
              taskName: "backup.verify",
              failedAt: "2026-08-04T13:30:00.000Z",
              error: "Backup verification failed."
            },
            {
              taskName: "operations.collect",
              failedAt: "2026-08-04T13:00:00.000Z",
              error: "Operations collection failed."
            }
          ]
        })}
      />
    );

    expect(markup).toContain("2 failures");
    expect(markup).toContain("backup.verify");
    expect(markup).toContain("operations.collect");
  });

  it("renders failures without timestamps safely", () => {
    const markup = renderToStaticMarkup(
      <SchedulerFailuresPanel
        scheduler={scheduler({
          failedCount: 1,
          recentFailures: [
            {
              taskName: "sports.maintenance",
              failedAt: null,
              error: "Maintenance failed."
            }
          ]
        })}
      />
    );

    expect(markup).toContain("sports.maintenance");
    expect(markup).toContain("Maintenance failed.");
    expect(markup).toContain("Time unavailable");
    expect(markup).not.toContain('dateTime=""');
  });

  it("renders unavailable scheduler detail", () => {
    const markup = renderToStaticMarkup(
      <SchedulerFailuresPanel
        scheduler={scheduler({
          status: "unavailable",
          detail: "Scheduler state could not be read.",
          registeredCount: null,
          enabledCount: null,
          disabledCount: null,
          dueCount: null,
          runningCount: null,
          failedCount: null,
          lastRunAt: null,
          nextRunAt: null,
          recentFailures: []
        })}
      />
    );

    expect(markup).toContain("Unavailable");
    expect(markup).toContain("Scheduler state could not be read.");
    expect(markup).not.toContain('class="status-list"');
  });
});
