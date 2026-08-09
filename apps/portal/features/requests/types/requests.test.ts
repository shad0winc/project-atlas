import { describe, expect, it } from "vitest";

import {
  createMediaRequest,
  createMediaRequestCollection,
  createRequestsState,
  replaceMediaRequest,
  type MediaRequest
} from "./requests";

const REQUEST_ID = "req_0123456789abcdef0123456789abcdef";
const USER_ID = "usr_0123456789abcdef0123456789abcdef";

function request(overrides: Partial<MediaRequest> = {}): MediaRequest {
  return {
    requestId: REQUEST_ID,
    userId: USER_ID,
    mediaType: "movie",
    provider: " Jellyseerr ",
    providerMediaId: " 157336 ",
    title: " Interstellar ",
    year: 2014,
    status: "approved",
    terminal: false,
    active: true,
    canCancel: true,
    recoveryRequired: false,
    createdAt: "2026-08-09T12:00:00Z",
    updatedAt: "2026-08-09T12:30:00Z",
    ...overrides
  };
}

describe("Personal Requests domain contract", () => {
  it("normalizes Request identity, provider, title, and timestamps", () => {
    expect(createMediaRequest(request())).toEqual({
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
      createdAt: "2026-08-09T12:00:00.000Z",
      updatedAt: "2026-08-09T12:30:00.000Z"
    });
  });

  it("rejects malformed Request and user identities", () => {
    expect(() =>
      createMediaRequest(
        request({
          requestId: "request-1"
        })
      )
    ).toThrow("request.requestId is invalid.");

    expect(() =>
      createMediaRequest(
        request({
          userId: "user-1"
        })
      )
    ).toThrow("request.userId is invalid.");
  });

  it("enforces terminal, active, and recovery lifecycle invariants", () => {
    expect(() =>
      createMediaRequest(
        request({
          status: "cancelled",
          terminal: false,
          active: true,
          canCancel: false
        })
      )
    ).toThrow("request.terminal does not match request.status.");

    expect(() =>
      createMediaRequest(
        request({
          status: "cancelling",
          recoveryRequired: false,
          canCancel: false
        })
      )
    ).toThrow("request.recoveryRequired does not match request.status.");

    expect(() =>
      createMediaRequest(
        request({
          status: "cancelling",
          recoveryRequired: true,
          canCancel: true
        })
      )
    ).toThrow("request.canCancel conflicts with request lifecycle state.");
  });

  it("requires availability time when the Request is available", () => {
    expect(() =>
      createMediaRequest(
        request({
          status: "available",
          terminal: true,
          active: false,
          canCancel: false
        })
      )
    ).toThrow("request.availableAt is required for available requests.");
  });

  it("fails closed when a collection crosses the authenticated owner", () => {
    expect(() =>
      createMediaRequestCollection(
        [
          request(),
          request({
            requestId: "req_abcdef0123456789abcdef0123456789",
            userId: "usr_abcdef0123456789abcdef0123456789"
          })
        ],
        USER_ID
      )
    ).toThrow("Media Requests response crossed the authenticated-user boundary.");
  });

  it("replaces one lifecycle record without changing collection identity", () => {
    const original = createMediaRequestCollection([request()], USER_ID);

    const cancelled = request({
      status: "cancelled",
      terminal: true,
      active: false,
      canCancel: false,
      updatedAt: "2026-08-09T13:00:00Z"
    });

    expect(replaceMediaRequest(original, cancelled, USER_ID)).toEqual([
      expect.objectContaining({
        requestId: REQUEST_ID,
        status: "cancelled",
        canCancel: false
      })
    ]);
  });

  it("distinguishes loading, ready-empty, and error states", () => {
    expect(createRequestsState(null, null)).toEqual({
      status: "loading"
    });

    expect(createRequestsState([], null)).toEqual({
      status: "ready",
      data: []
    });

    expect(createRequestsState(null, new Error("Unavailable"))).toMatchObject({
      status: "error"
    });
  });
});
