import { afterEach, describe, expect, it, vi } from "vitest";
import { AtlasApiError } from "../../../lib/api/errors";
import { withSportsBudgetRetry, withSportsScheduleBudgetRetry } from "./budgetRetry";

const failure = (seconds: number) => new AtlasApiError({ status: 429, detail: "fixture", method: "GET", path: "/sports/events", requestId: "fixture", kind: "rate-limit", retryAfterSeconds: seconds });
const clock = () => {
  let time = 0;
  return { now: () => time, wait: async (milliseconds: number) => { time += milliseconds; } };
};
afterEach(() => vi.useRealTimers());

describe("multi-league schedule continuation", () => {
  it("continues beyond three attempts while search remains bounded", async () => {
    const task = vi.fn().mockRejectedValueOnce(failure(10)).mockRejectedValueOnce(failure(10)).mockRejectedValueOnce(failure(10)).mockResolvedValue("complete");
    await expect(withSportsScheduleBudgetRetry(task, {}, clock())).resolves.toBe("complete");
    expect(task).toHaveBeenCalledTimes(4);
    const search = vi.fn().mockRejectedValue(failure(10));
    await expect(withSportsBudgetRetry(search, {}, clock())).rejects.toBeInstanceOf(AtlasApiError);
    expect(search).toHaveBeenCalledTimes(3);
  });
  it("honors a provider cooldown without a tight retry loop", async () => {
    const task = vi.fn().mockRejectedValue(failure(300));
    await expect(withSportsScheduleBudgetRetry(task, {}, clock())).rejects.toBeInstanceOf(AtlasApiError);
    expect(task).toHaveBeenCalledTimes(1);
  });
  it("caps schedule retries at twelve", async () => {
    const task = vi.fn().mockRejectedValue(failure(1));
    await expect(withSportsScheduleBudgetRetry(task, {}, clock())).rejects.toBeInstanceOf(AtlasApiError);
    expect(task).toHaveBeenCalledTimes(12);
  });
  it("caps cumulative waits at ninety seconds", async () => {
    const task = vi.fn().mockRejectedValue(failure(30));
    await expect(withSportsScheduleBudgetRetry(task, {}, clock())).rejects.toBeInstanceOf(AtlasApiError);
    expect(task).toHaveBeenCalledTimes(4);
  });
  it("aborts in-flight work at the two-minute deadline", async () => {
    vi.useFakeTimers();
    const task = (signal: AbortSignal) => new Promise<void>((resolve, reject) => {
      void resolve;
      signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    });
    const result = expect(withSportsScheduleBudgetRetry(task)).rejects.toMatchObject({ name: "TimeoutError" });
    await vi.advanceTimersByTimeAsync(120_000);
    await result;
    expect(vi.getTimerCount()).toBe(0);
  });
});
