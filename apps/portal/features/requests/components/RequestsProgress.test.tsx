// @vitest-environment happy-dom
import { act } from "react";
import { createRoot } from "react-dom/client";
import { vi } from "vitest";
import {
  renderToStaticMarkup
} from "react-dom/server";

import {
  describe,
  expect,
  it
} from "vitest";

import {
  createMediaRequest,
  type MediaRequest,
  type MediaRequestStatus
} from "../types/requests";

import {
  RequestsContent
} from "./RequestsView";

const REQUEST_ID = "req_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function request(
  overrides: Partial<MediaRequest> = {}
): MediaRequest {
  return createMediaRequest({
    requestId: REQUEST_ID,
    userId: USER_ID,
    mediaType: "movie",
    provider: "jellyseerr",
    providerMediaId: "157336",
    title: "Interstellar",
    year: 2014,
    status: "approved",
    terminal: false,
    active: true,
    canCancel: true,
    recoveryRequired: false,
    createdAt: "2026-09-13T04:00:00Z",
    updatedAt: "2026-09-13T04:30:00Z",
    ...overrides
  });
}

function renderRequest(
  mediaRequest: MediaRequest
): string {
  return renderToStaticMarkup(
    <RequestsContent
      blockedCancellationIds={[]}
      canCancel={true}
      cancellingRequestId={null}
      mutationFailure={null}
      onBeginCancellation={() => undefined}
      onCancelConfirmation={() => undefined}
      onConfirmCancellation={() => undefined}
      onRetry={() => undefined}
      pendingCancellationId={null}
      state={{
        status: "ready",
        data: [mediaRequest]
      }}
    />
  );
}

describe("Request lifecycle progress presentation", () => {
  it.each(["available", "cancelled"] as const)(
    "moves a %s request into history exactly 24 hours after its status change",
    async status => {
      vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
      vi.useFakeTimers();
      vi.setSystemTime(new Date("2026-09-14T04:44:59Z"));
      const container = document.createElement("div");
      const root = createRoot(container);
      const completedAt = "2026-09-13T04:45:00Z";
      const completed = request({
        status, terminal: true, active: false, canCancel: false,
        updatedAt: completedAt,
        ...(status === "available" ? { availableAt: completedAt } : {})
      });
      try {
        await act(async () => root.render(
          <RequestsContent
            blockedCancellationIds={[]} canCancel={true} cancellingRequestId={null}
            mutationFailure={null} onBeginCancellation={() => undefined}
            onCancelConfirmation={() => undefined} onConfirmCancellation={() => undefined}
            onRetry={() => undefined} pendingCancellationId={null}
            state={{ status: "ready", data: [completed] }}
          />
        ));
        await act(async () => vi.advanceTimersByTimeAsync(999));
        expect(container.querySelector('[aria-label="Your media requests"]')?.textContent).toContain("Interstellar");
        expect(container.querySelector("details")).toBeNull();
        await act(async () => vi.advanceTimersByTimeAsync(1));
        expect(container.querySelector('[aria-label="Your media requests"]')?.textContent).not.toContain("Interstellar");
        expect(container.querySelector("details summary")?.textContent).toBe("Archived requests (1)");
        expect(container.querySelector('[aria-label="Archived media requests"]')?.textContent).toContain("Interstellar");
      } finally {
        await act(async () => root.unmount());
        vi.useRealTimers();
        vi.unstubAllGlobals();
      }
    }
  );

  it("renders Processing in Jellyfin as the current request stage", () => {
    const markup = renderRequest(
      request({
        status: "processing",
        updatedAt: "2026-09-13T04:40:00Z"
      })
    );

    expect(markup).toContain(
      'aria-label="Request progress"'
    );

    expect(markup).toContain(
      ">Processing in Jellyfin<"
    );

    expect(markup).toContain(
      ">Ready to Watch<"
    );

    for (
      const stage of [
        "requested",
        "approved",
        "searching",
        "downloading",
        "importing"
      ]
    ) {
      expect(markup).toMatch(
        new RegExp(
          `data-stage="${stage}"[^>]*data-stage-state="complete"`
        )
      );
    }

    expect(markup).toMatch(
      /data-stage="processing"[^>]*data-stage-state="current"/
    );

    expect(markup).toMatch(
      /data-stage="available"[^>]*data-stage-state="pending"/
    );

    // Do not invent downloader percentages until Atlas has a
    // proven request -> downloader-job correlation.
    expect(markup).not.toContain(
      "request-progress-percent"
    );
    expect(markup).not.toContain("%");
  });

  it("renders Ready to Watch as the completed lifecycle destination", () => {
    const markup = renderRequest(
      request({
        status: "available",
        terminal: true,
        active: false,
        canCancel: false,
        updatedAt: "2026-09-13T04:45:00Z",
        availableAt: "2026-09-13T04:45:00Z"
      })
    );

    expect(markup).toContain(
      ">Ready to Watch<"
    );

    expect(markup).toMatch(
      /data-stage="available"[^>]*data-stage-state="current"/
    );
  });

  it.each(
    [
      "submitting",
      "cancelling",
      "failed",
      "cancelled"
    ] satisfies readonly MediaRequestStatus[]
  )(
    "does not present %s as forward lifecycle progress",
    (status) => {
      const terminal = (
        status === "failed"
        || status === "cancelled"
      );

      const markup = renderRequest(
        request({
          status,
          terminal,
          active: !terminal,
          canCancel: false,
          recoveryRequired: (
            status === "submitting"
            || status === "cancelling"
          )
        })
      );

      expect(markup).not.toContain(
        'aria-label="Request progress"'
      );
    }
  );
});
