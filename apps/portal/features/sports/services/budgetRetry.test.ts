import { afterEach, describe, expect, it, vi } from "vitest";
import { AtlasApiError } from "../../../lib/api/errors";
import { withSportsBudgetRetry } from "./budgetRetry";

const failure = (seconds: number | null, status = 429) => new AtlasApiError({
  status, detail: "fixture", method: "GET", path: "/sports/events", requestId: "fixture",
  kind: status === 429 ? "rate-limit" : "unavailable", retryAfterSeconds: seconds,
});
const immediateClock = () => {
  let epoch = 0;
  const waits: number[] = [];
  return { waits, now: () => epoch, wait: async (milliseconds: number) => {
    waits.push(milliseconds); epoch += milliseconds;
  } };
};
afterEach(() => vi.useRealTimers());

describe("bounded Sports budget pacing", () => {
  it("continues the same GET after the exact server hint", async () => {
    const clock = immediateClock();
    const task = vi.fn().mockRejectedValueOnce(failure(10)).mockResolvedValue("ready");
    await expect(withSportsBudgetRetry(task, {}, clock)).resolves.toBe("ready");
    expect(clock.waits).toEqual([10_000]);
    expect(task).toHaveBeenCalledTimes(2);
  });
  it("stops after three attempts and at most twenty seconds of waits", async () => {
    const clock = immediateClock();
    const error = failure(10);
    const task = vi.fn().mockRejectedValue(error);
    await expect(withSportsBudgetRetry(task, {}, clock)).rejects.toBe(error);
    expect(task).toHaveBeenCalledTimes(3);
    expect(clock.waits).toEqual([10_000, 10_000]);
  });
  it.each([null, 21, 120])("does not retry a missing or excessive hint: %s", async seconds => {
    const clock = immediateClock();
    const error = failure(seconds);
    const task = vi.fn().mockRejectedValue(error);
    await expect(withSportsBudgetRetry(task, {}, clock)).rejects.toBe(error);
    expect(task).toHaveBeenCalledTimes(1);
    expect(clock.waits).toEqual([]);
  });
  it.each([401, 403, 503])("does not retry HTTP %s", async status => {
    const task = vi.fn().mockRejectedValue(failure(1, status));
    await expect(withSportsBudgetRetry(task)).rejects.toBeInstanceOf(AtlasApiError);
    expect(task).toHaveBeenCalledTimes(1);
  });
  it("does not retry a network failure", async () => {
    const error = new TypeError("network fixture");
    const task = vi.fn().mockRejectedValue(error);
    await expect(withSportsBudgetRetry(task)).rejects.toBe(error);
    expect(task).toHaveBeenCalledTimes(1);
  });
  it("does not start an already cancelled operation", async () => {
    const controller = new AbortController(); controller.abort();
    const task = vi.fn();
    await expect(withSportsBudgetRetry(task, { signal: controller.signal })).rejects.toMatchObject({ name: "AbortError" });
    expect(task).not.toHaveBeenCalled();
  });
  it("cancels a pending wait without issuing another GET", async () => {
    vi.useFakeTimers();
    const controller = new AbortController();
    const task = vi.fn().mockRejectedValue(failure(10));
    const result = withSportsBudgetRetry(task, { signal: controller.signal });
    const check = expect(result).rejects.toMatchObject({ name: "AbortError" });
    await vi.advanceTimersByTimeAsync(1);
    controller.abort(); await check;
    await vi.advanceTimersByTimeAsync(20_000);
    expect(task).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(0);
  });
  it("cancels an in-flight request at the overall thirty-second deadline", async () => {
    vi.useFakeTimers();
    const task = (signal: AbortSignal) => new Promise<void>((resolve, reject) => {
      void resolve;
      signal.addEventListener("abort", () => reject(signal.reason), { once: true });
    });
    const check = expect(withSportsBudgetRetry(task)).rejects.toMatchObject({ name: "TimeoutError" });
    await vi.advanceTimersByTimeAsync(30_000); await check;
    expect(vi.getTimerCount()).toBe(0);
  });
  it("refuses a wait that would exceed the operation deadline", async () => {
    const error = failure(10); const waits = vi.fn(); let reads = 0;
    const task = vi.fn().mockRejectedValue(error);
    await expect(withSportsBudgetRetry(task, {}, {
      now: () => reads++ === 0 ? 0 : 25_000, wait: waits,
    })).rejects.toBe(error);
    expect(waits).not.toHaveBeenCalled();
  });
});
