import { beforeEach, describe, expect, it, vi } from "vitest";

import type { MediaRetention } from "../types/retention";

const {
  addFavoriteMock,
  addDislikeMock,
  refreshMediaRetentionAfterMutationMock
} = vi.hoisted(() => ({
  addFavoriteMock: vi.fn(),
  addDislikeMock: vi.fn(),
  refreshMediaRetentionAfterMutationMock: vi.fn()
}));

vi.mock("../../favorites", () => ({
  addFavorite: addFavoriteMock
}));

vi.mock("../../dislikes/api/dislikes", () => ({
  addDislike: addDislikeMock
}));

vi.mock("./retention-refresh", () => ({
  refreshMediaRetentionAfterMutation:
    refreshMediaRetentionAfterMutationMock
}));

import {
  addFavoriteAndRefreshRetention,
  addDislikeAndNotify
} from "./retention-mutations";

const retention: MediaRetention = {
  provider: "jellyfin",
  itemId: "item-123",
  eligible: false,
  retained: true,
  lifecycle: {
    state: "protected",
    rule: "policy_protected",
    basisAt: null,
    deleteAt: null
  }
};

describe("addFavoriteAndRefreshRetention", () => {
  beforeEach(() => {
    addFavoriteMock.mockReset();
    addDislikeMock.mockReset();
    refreshMediaRetentionAfterMutationMock.mockReset();
  });

  it("refreshes authoritative retention only after Favorite mutation succeeds", async () => {
    const order: string[] = [];

    addFavoriteMock.mockImplementationOnce(async () => {
      order.push("favorite");
      return {};
    });

    refreshMediaRetentionAfterMutationMock.mockImplementationOnce(
      async () => {
        order.push("retention");
        return {
          status: "available",
          retention
        };
      }
    );

    const result =
      await addFavoriteAndRefreshRetention(
        {
          provider: "jellyfin",
          itemId: "item-123"
        },
        {
          expectedUserId:
            "usr_0123456789abcdef0123456789abcdef"
        }
      );

    expect(order).toEqual([
      "favorite",
      "retention"
    ]);

    expect(addFavoriteMock).toHaveBeenCalledTimes(1);

    expect(refreshMediaRetentionAfterMutationMock)
      .toHaveBeenCalledTimes(1);

    expect(refreshMediaRetentionAfterMutationMock)
      .toHaveBeenCalledWith(
        "jellyfin",
        "item-123"
      );

    expect(result).toEqual({
      status: "available",
      retention
    });
  });

  it("does not refresh retention when Favorite mutation fails", async () => {
    addFavoriteMock.mockRejectedValueOnce(
      new Error("Favorite failed.")
    );

    await expect(
      addFavoriteAndRefreshRetention(
        {
          provider: "jellyfin",
          itemId: "item-123"
        },
        {
          expectedUserId:
            "usr_0123456789abcdef0123456789abcdef"
        }
      )
    ).rejects.toThrow("Favorite failed.");

    expect(
      refreshMediaRetentionAfterMutationMock
    ).not.toHaveBeenCalled();
  });

  it("preserves successful Favorite mutation when retention refresh is unavailable", async () => {
    addFavoriteMock.mockResolvedValueOnce({});

    refreshMediaRetentionAfterMutationMock
      .mockResolvedValueOnce({
        status: "unavailable",
        retention: null
      });

    await expect(
      addFavoriteAndRefreshRetention(
        {
          provider: "jellyfin",
          itemId: "item-123"
        },
        {
          expectedUserId:
            "usr_0123456789abcdef0123456789abcdef"
        }
      )
    ).resolves.toEqual({
      status: "unavailable",
      retention: null
    });

    expect(addFavoriteMock).toHaveBeenCalledTimes(1);
  });
});

describe("addDislikeAndNotify", () => {
  beforeEach(() => {
    addFavoriteMock.mockReset();
    addDislikeMock.mockReset();
    refreshMediaRetentionAfterMutationMock.mockReset();
  });

  it("invokes the success callback only after Dislike mutation succeeds", async () => {
    const order: string[] = [];

    addDislikeMock.mockImplementationOnce(async () => {
      order.push("dislike");
      return {};
    });

    const onDisliked = vi.fn(async () => {
      order.push("callback");
    });

    await addDislikeAndNotify(
      {
        provider: "jellyfin",
        itemId: "item-123"
      },
      {
        expectedUserId:
          "usr_0123456789abcdef0123456789abcdef"
      },
      onDisliked
    );

    expect(order).toEqual([
      "dislike",
      "callback"
    ]);

    expect(onDisliked).toHaveBeenCalledTimes(1);
  });

  it("does not invoke the success callback when Dislike mutation fails", async () => {
    addDislikeMock.mockRejectedValueOnce(
      new Error("Dislike failed.")
    );

    const onDisliked = vi.fn();

    await expect(
      addDislikeAndNotify(
        {
          provider: "jellyfin",
          itemId: "item-123"
        },
        {
          expectedUserId:
            "usr_0123456789abcdef0123456789abcdef"
        },
        onDisliked
      )
    ).rejects.toThrow("Dislike failed.");

    expect(onDisliked).not.toHaveBeenCalled();
  });

  it("does not rewrite a successful Dislike as failed when its post-success callback fails", async () => {
    addDislikeMock.mockResolvedValueOnce({});

    const onDisliked = vi.fn().mockRejectedValueOnce(
      new Error("Retention refresh unavailable.")
    );

    await expect(
      addDislikeAndNotify(
        {
          provider: "jellyfin",
          itemId: "item-123"
        },
        {
          expectedUserId:
            "usr_0123456789abcdef0123456789abcdef"
        },
        onDisliked
      )
    ).resolves.toBeUndefined();

    expect(addDislikeMock).toHaveBeenCalledTimes(1);
    expect(onDisliked).toHaveBeenCalledTimes(1);
  });

  it("supports successful Dislike mutation without a callback", async () => {
    addDislikeMock.mockResolvedValueOnce({});

    await expect(
      addDislikeAndNotify(
        {
          provider: "jellyfin",
          itemId: "item-123"
        },
        {
          expectedUserId:
            "usr_0123456789abcdef0123456789abcdef"
        }
      )
    ).resolves.toBeUndefined();

    expect(addDislikeMock).toHaveBeenCalledTimes(1);
  });
});
