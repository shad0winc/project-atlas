import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { DownloadsState } from "../../downloads/types/downloads";

const { canMock, useDownloadsMock } = vi.hoisted(() => ({
  canMock: vi.fn<(permission: string) => boolean>(),
  useDownloadsMock: vi.fn()
}));

vi.mock("../../../lib/authorization", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../lib/authorization")>();

  return {
    ...actual,
    usePermission: () => ({
      grantedPermissionPatterns: [],
      deniedPermissionPatterns: [],
      can: canMock,
      canAny: () => false,
      canEvery: () => false
    })
  };
});

vi.mock("../../downloads/hooks/use-downloads", () => ({
  useDownloads: useDownloadsMock
}));

import { DownloadManagementView } from "./DownloadManagementView";

function readyState(state: "queued" | "seeding" | "completed" | "paused"): DownloadsState {
  return {
    status: "ready",
    data: {
      schemaVersion: 1,
      generatedAt: "2026-08-30T03:50:00Z",
      summary: {
        active: 0,
        queued: state === "queued" ? 1 : 0,
        completed: state === "completed" || state === "seeding" ? 1 : 0,
        error: 0,
        downloadRate: 0,
        uploadRate: 0
      },
      downloads: [
        {
          jobId: "dl_0123456789abcdef0123456789abcdef",
          name: "Example Job",
          category: "anime-tv",
          state,
          progress: 1,
          totalBytes: 1024,
          downloadedBytes: 1024,
          downloadRate: 0,
          uploadRate: 0,
          etaSeconds: null
        }
      ]
    }
  };
}

function renderState(state: "queued" | "seeding" | "completed" | "paused"): string {
  useDownloadsMock.mockReturnValue({
    state: readyState(state),
    refresh: vi.fn()
  });

  return renderToStaticMarkup(<DownloadManagementView />);
}

function buttonMarkup(markup: string, label: string): string {
  const match = markup.match(
    new RegExp(`<button[^>]*>${label}</button>`)
  );

  if (!match) {
    throw new Error(`Could not find ${label} button`);
  }

  return match[0];
}

describe("DownloadManagementView controls", () => {
  beforeEach(() => {
    canMock.mockReset();
    useDownloadsMock.mockReset();
    canMock.mockReturnValue(true);
  });

  it("treats queued upload jobs as resumable seeding work", () => {
    const markup = renderState("queued");

    expect(markup).toContain("State: queued");

    expect(buttonMarkup(markup, "Stop seeding")).not.toContain("disabled");
    expect(buttonMarkup(markup, "Resume")).toContain("disabled");
    expect(buttonMarkup(markup, "Remove job")).not.toContain("disabled");

    expect(markup).not.toContain("dl_0123456789abcdef0123456789abcdef");
  });

  it("allows stopping active seeding but not resuming it", () => {
    const markup = renderState("seeding");

    expect(buttonMarkup(markup, "Stop seeding")).not.toContain("disabled");
    expect(buttonMarkup(markup, "Resume")).toContain("disabled");
    expect(buttonMarkup(markup, "Remove job")).not.toContain("disabled");
  });

  it("allows resuming a completed upload job", () => {
    const markup = renderState("completed");

    expect(buttonMarkup(markup, "Stop seeding")).toContain("disabled");
    expect(buttonMarkup(markup, "Resume")).not.toContain("disabled");
    expect(buttonMarkup(markup, "Remove job")).not.toContain("disabled");
  });
});
