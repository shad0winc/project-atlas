import { afterEach, describe, expect, it, vi } from "vitest";

import {
  logoutAtlasSession,
  requestAtlasPasswordRecovery,
  resetAtlasPassword
} from "./auth";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Atlas authentication services", () => {
  it("revokes the normalized refresh token on logout", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(null, {
        status: 204
      })
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(logoutAtlasSession("  refresh-token  ")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledOnce();

    const [path, options] = fetchMock.mock.calls[0] as [string, RequestInit];

    expect(path).toBe("/api/v1/auth/logout");
    expect(options.method).toBe("POST");
    expect(options.cache).toBe("no-store");
    expect(options.body).toBe(
      JSON.stringify({
        refresh_token: "refresh-token"
      })
    );
  });

  it("rejects an empty refresh token without making a request", async () => {
    const fetchMock = vi.fn();

    vi.stubGlobal("fetch", fetchMock);

    await expect(logoutAtlasSession("   ")).rejects.toThrow("Atlas refresh token cannot be empty.");

    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("Atlas password recovery services", () => {
  it("requests password recovery with normalized email", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "accepted",
          message:
            "If an Atlas account exists for that email, a password reset link has been sent."
        }),
        {
          status: 202,
          headers: {
            "Content-Type": "application/json"
          }
        }
      )
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      requestAtlasPasswordRecovery(
        "  member@example.test  "
      )
    ).resolves.toEqual({
      status: "accepted",
      message:
        "If an Atlas account exists for that email, a password reset link has been sent."
    });

    expect(fetchMock).toHaveBeenCalledOnce();

    const [requestPath, options] =
      fetchMock.mock.calls[0] as [
        string,
        RequestInit
      ];

    expect(requestPath).toBe(
      "/api/v1/auth/password-recovery/request"
    );
    expect(options.method).toBe("POST");
    expect(options.cache).toBe("no-store");
    expect(options.body).toBe(
      JSON.stringify({
        email: "member@example.test"
      })
    );
  });

  it("rejects blank recovery email without a request", async () => {
    const fetchMock = vi.fn();

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      requestAtlasPasswordRecovery("   ")
    ).rejects.toThrow("Email cannot be empty.");

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("submits recovery token and new password", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          status: "password-reset"
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json"
          }
        }
      )
    );

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      resetAtlasPassword({
        token: "  atlas_reset_example  ",
        newPassword: "new-password"
      })
    ).resolves.toEqual({
      status: "password-reset"
    });

    expect(fetchMock).toHaveBeenCalledOnce();

    const [requestPath, options] =
      fetchMock.mock.calls[0] as [
        string,
        RequestInit
      ];

    expect(requestPath).toBe(
      "/api/v1/auth/password-recovery/reset"
    );
    expect(options.method).toBe("POST");
    expect(options.cache).toBe("no-store");
    expect(options.body).toBe(
      JSON.stringify({
        token: "atlas_reset_example",
        new_password: "new-password"
      })
    );
  });

  it("rejects blank reset token without a request", async () => {
    const fetchMock = vi.fn();

    vi.stubGlobal("fetch", fetchMock);

    await expect(
      resetAtlasPassword({
        token: " ",
        newPassword: "new-password"
      })
    ).rejects.toThrow(
      "Password recovery token cannot be empty."
    );

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
