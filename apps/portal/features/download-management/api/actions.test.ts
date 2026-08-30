import { beforeEach, describe, expect, it, vi } from "vitest";

const { authenticatedAtlasApiRequestMock } = vi.hoisted(() => ({
  authenticatedAtlasApiRequestMock: vi.fn()
}));

vi.mock("../../../lib/services/authenticated", () => ({
  authenticatedAtlasApiRequest: authenticatedAtlasApiRequestMock
}));

import { runDownloadManagementAction } from "./actions";

const JOB_ID = "dl_0123456789abcdef0123456789abcdef";

describe("download management actions", () => {
  beforeEach(() => authenticatedAtlasApiRequestMock.mockReset());

  it("sends a bounded authenticated mutation with automatic retries disabled", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({ status: "accepted", action: "stop_seeding", job_id: JOB_ID });
    await expect(
      runDownloadManagementAction(JOB_ID, "stop_seeding")
    ).resolves.toEqual({
      accepted: true,
      action: "stop_seeding",
      jobId: JOB_ID
    });

    expect(authenticatedAtlasApiRequestMock).toHaveBeenCalledWith(
      "/admin/downloads/action",
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        body: { job_id: JOB_ID, action: "stop_seeding" },
        retryPolicy: expect.objectContaining({ maxRetries: 0 })
      })
    );
  });

  it("rejects invalid opaque identifiers before transport", async () => {
    await expect(runDownloadManagementAction("raw-qbit-hash", "resume")).rejects.toThrow("identifier is invalid");
    expect(authenticatedAtlasApiRequestMock).not.toHaveBeenCalled();
  });

  it("fails closed when the response does not match the requested job", async () => {
    authenticatedAtlasApiRequestMock.mockResolvedValue({ status: "accepted", action: "resume", job_id: "dl_abcdefabcdefabcdefabcdefabcdefab" });
    await expect(runDownloadManagementAction(JOB_ID, "resume")).rejects.toThrow("did not match");
  });
});
