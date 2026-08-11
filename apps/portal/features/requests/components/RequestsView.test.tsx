import { renderToStaticMarkup } from "react-dom/server";

import { describe, expect, it } from "vitest";

import { createMediaRequest, type MediaRequest } from "../types/requests";

import { RequestsContent } from "./RequestsView";

const REQUEST_ID = "req_0123456789abcdef0123456789abcdef";

const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function request(overrides: Partial<MediaRequest> = {}): MediaRequest {
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
    createdAt: "2026-08-09T12:00:00Z",
    updatedAt: "2026-08-09T12:30:00Z",
    ...overrides
  });
}

const callbacks = {
  onRetry: () => undefined,
  onBeginCancellation: () => undefined,
  onCancelConfirmation: () => undefined,
  onConfirmCancellation: () => undefined
};

describe("Personal Requests presentation", () => {
  it("renders accessible loading content", () => {
    const markup = renderToStaticMarkup(
      <RequestsContent
        {...callbacks}
        blockedCancellationIds={[]}
        canCancel={true}
        cancellingRequestId={null}
        mutationFailure={null}
        pendingCancellationId={null}
        state={{
          status: "loading"
        }}
      />
    );

    expect(markup).toContain('aria-busy="true"');

    expect(markup).toContain('aria-label="Loading requests"');
  });

  it("renders an actionable load error", () => {
    const markup = renderToStaticMarkup(
      <RequestsContent
        {...callbacks}
        blockedCancellationIds={[]}
        canCancel={true}
        cancellingRequestId={null}
        mutationFailure={null}
        pendingCancellationId={null}
        state={{
          status: "error",
          error: new Error("Requests failed.")
        }}
      />
    );

    expect(markup).toContain('role="alert"');

    expect(markup).toContain("Requests failed.");

    expect(markup).toContain("Try again");
  });

  it("renders an empty request history distinctly from an error", () => {
    const markup = renderToStaticMarkup(
      <RequestsContent
        {...callbacks}
        blockedCancellationIds={[]}
        canCancel={true}
        cancellingRequestId={null}
        mutationFailure={null}
        pendingCancellationId={null}
        state={{
          status: "ready",
          data: []
        }}
      />
    );

    expect(markup).toContain("Your request history is empty");

    expect(markup).not.toContain('role="alert"');
  });

  it("shows lifecycle details while withholding cancellation from read-only users", () => {
    const markup = renderToStaticMarkup(
      <RequestsContent
        {...callbacks}
        blockedCancellationIds={[]}
        canCancel={false}
        cancellingRequestId={null}
        mutationFailure={null}
        pendingCancellationId={null}
        state={{
          status: "ready",
          data: [request()]
        }}
      />
    );

    expect(markup).toContain("Interstellar");

    expect(markup).toContain("Approved");

    expect(markup).toContain("does not have permission to cancel");

    expect(markup).not.toContain(">Cancel request<");
  });

  it("requires explicit confirmation before cancellation", () => {
    const markup = renderToStaticMarkup(
      <RequestsContent
        {...callbacks}
        blockedCancellationIds={[]}
        canCancel={true}
        cancellingRequestId={null}
        mutationFailure={null}
        pendingCancellationId={REQUEST_ID}
        state={{
          status: "ready",
          data: [request()]
        }}
      />
    );

    expect(markup).toContain("Confirm cancellation");

    expect(markup).toContain("Keep request");
  });

  it("never renders cancellation for a server recovery-required Request", () => {
    const markup = renderToStaticMarkup(
      <RequestsContent
        {...callbacks}
        blockedCancellationIds={[]}
        canCancel={true}
        cancellingRequestId={null}
        mutationFailure={null}
        pendingCancellationId={null}
        state={{
          status: "ready",
          data: [
            request({
              status: "cancelling",
              canCancel: false,
              recoveryRequired: true
            })
          ]
        }}
      />
    );

    expect(markup).toContain("recovery-required lifecycle state");

    expect(markup).toContain("Do not repeat");

    expect(markup).not.toContain(">Cancel request<");
  });

  it("blocks another cancellation locally after an unconfirmed mutation", () => {
    const markup = renderToStaticMarkup(
      <RequestsContent
        {...callbacks}
        blockedCancellationIds={[REQUEST_ID]}
        canCancel={true}
        cancellingRequestId={null}
        mutationFailure={{
          requestId: REQUEST_ID,
          reconciliationRequired: false,
          error: new Error("Refresh request status before attempting another cancellation.")
        }}
        pendingCancellationId={null}
        state={{
          status: "ready",
          data: [request()]
        }}
      />
    );

    expect(markup).toContain("Cancellation was not confirmed");

    expect(markup).toContain("Refresh request status");

    expect(markup).not.toContain(">Cancel request<");
  });

  it("surfaces reconciliation without a retry action", () => {
    const markup = renderToStaticMarkup(
      <RequestsContent
        {...callbacks}
        blockedCancellationIds={[REQUEST_ID]}
        canCancel={true}
        cancellingRequestId={null}
        mutationFailure={{
          requestId: REQUEST_ID,
          reconciliationRequired: true,
          error: new Error(
            "Media request cancellation requires reconciliation. Do not retry this request."
          )
        }}
        pendingCancellationId={null}
        state={{
          status: "ready",
          data: [request()]
        }}
      />
    );

    expect(markup).toContain("Request requires reconciliation");

    expect(markup).toContain("Do not retry this request.");

    expect(markup).not.toContain("Try cancellation again");
  });
});
