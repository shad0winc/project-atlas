import { it } from "vitest";
import assert from "node:assert/strict";
import { createTerminalLiveRelease } from "./terminalLiveRelease";
import type { SportsLiveSessionResult } from "./sports";

function owned(id = "one"): SportsLiveSessionResult {
  return { liveSessionId: id, session: { playableTargetId: "same-feed" },
    releaseCapability: "private-fixture" } as SportsLiveSessionResult;
}

it("ignores a stale callback even for the same target", () => {
  const gate = createTerminalLiveRelease();
  const old = owned(), current = owned("two");
  assert.equal(gate.markFailed(current, old.session), false);
  assert.equal(gate.current(), null);
  assert.equal(gate.markFailed(null, old.session), false);
});

it("blocks late heartbeats only for the failed owner and ignores duplicate errors", () => {
  const gate = createTerminalLiveRelease(), session = owned();
  assert.equal(gate.markFailed(session, session.session), true);
  assert.equal(gate.markFailed(session, session.session), false);
  assert.equal(gate.blocksHeartbeat("one"), true);
  assert.equal(gate.blocksHeartbeat("two"), false);
});

it("joins concurrent cleanup calls and passes the exact retained credential", async () => {
  const gate = createTerminalLiveRelease(), session = owned();
  gate.markFailed(session, session.session);
  let finish!: () => void;
  let calls = 0;
  const close = (value: SportsLiveSessionResult) => {
    calls++;
    assert.equal(value, session);
    assert.equal(value.releaseCapability, "private-fixture");
    return new Promise<void>((resolve) => { finish = resolve; });
  };
  const first = gate.release(close), second = gate.release(close);
  assert.equal(first, second);
  await Promise.resolve();
  assert.equal(calls, 1);
  assert.equal(gate.current(), session);
  finish();
  assert.equal(await first, true);
  assert.equal(gate.current(), null);
  assert.equal(gate.blocksHeartbeat("one"), false);
});

it("retains ownership after uncertain release and retries only when called again", async () => {
  const gate = createTerminalLiveRelease(), session = owned();
  gate.markFailed(session, session.session);
  let calls = 0;
  assert.equal(await gate.release(async () => { calls++; throw new Error("503"); }), false);
  await Promise.resolve();
  assert.equal(calls, 1);
  assert.equal(gate.current(), session);
  assert.equal(gate.blocksHeartbeat("one"), true);
  assert.equal(await gate.release(async (value) => { assert.equal(value, session); }), true);
  assert.equal(gate.current(), null);
});

it("retains ownership if cleanup throws synchronously", async () => {
  const gate = createTerminalLiveRelease(), session = owned();
  gate.markFailed(session, session.session);
  assert.equal(await gate.release(() => { throw new Error("fixture"); }), false);
  assert.equal(gate.current(), session);
});

it("does not release without failure and can handle a later independent session", async () => {
  const gate = createTerminalLiveRelease();
  assert.equal(await gate.release(async () => { throw new Error("must not call"); }), true);
  for (const id of ["one", "two"]) {
    const session = owned(id);
    assert.equal(gate.markFailed(session, session.session), true);
    assert.equal(await gate.release(async () => undefined), true);
  }
});
