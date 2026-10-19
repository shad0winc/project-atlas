import { readFileSync } from "node:fs";
import vm from "node:vm";
import { describe, expect, it, vi } from "vitest";

const source = readFileSync(new URL("../../../infra/caddy/site/maintenance/admin.js", import.meta.url), "utf8");
const enabled = { enabled: true, recovery_held: false, transition_pending: false, state_uncertain: false };

function response(status: number, body: unknown = null) {
  return { status, ok: status >= 200 && status < 300, json: async () => body };
}
function fixture(queue: ReturnType<typeof response>[]) {
  const nodes = new Map<string, { hidden: boolean; disabled: boolean; textContent: string; value: string; listeners: Record<string, (event?: unknown) => void>; addEventListener: (name: string, fn: (event?: unknown) => void) => void }>();
  const get = (id: string) => {
    let node = nodes.get(id);
    if (!node) {
      node = { hidden: false, disabled: false, textContent: "", value: "", listeners: {}, addEventListener(name, fn) { this.listeners[name] = fn; } };
      nodes.set(id, node);
    }
    return node;
  };
  const fetch = vi.fn(async () => {
    const next = queue.shift();
    if (!next) throw new Error("Unexpected request");
    return next;
  });
  const locks = vi.fn(async (_name: string, callback: () => Promise<unknown>) => callback());
  const storage = new Proxy({}, { get() { throw new Error("Credential persistence is prohibited"); } });
  vm.runInNewContext(source, { document: { getElementById: get }, navigator: { locks: { request: locks } }, fetch,
    localStorage: storage, sessionStorage: storage });
  return { get, fetch, locks, queue };
}
const settled = async () => { for (let index = 0; index < 30; index += 1) await Promise.resolve(); };

// These execute the actual shipped script against browser boundaries, not a rewritten copy.
describe("maintenance administration console", () => {
  it("restores a session and prevents disable while recovery is held", async () => {
    const f = fixture([response(200, { access_token: "access", token_type: "bearer" }), response(200, { ...enabled, recovery_held: true })]);
    await settled();
    expect(f.get("controls").hidden).toBe(false);
    expect(f.get("disable").disabled).toBe(true);
    expect(f.get("recovery-status").textContent).toContain("cannot be turned off");
    expect(f.locks).toHaveBeenCalledWith("atlas-browser-session", expect.any(Function));
  });
  it("submits credentials through the existing browser endpoint and clears the password", async () => {
    const f = fixture([response(401)]);
    await settled();
    f.queue.push(response(200, { access_token: "access", token_type: "bearer" }), response(200, enabled));
    f.get("username").value = "admin";
    f.get("password").value = "example";
    f.get("login").listeners.submit({ preventDefault() {} });
    await settled();
    expect(f.get("password").value).toBe("");
    expect(f.get("controls").hidden).toBe(false);
    const calls = f.fetch.mock.calls as unknown as [string, RequestInit][];
    expect(calls[1][0]).toBe("/api/v1/auth/browser/login");
    expect(calls[1][1].credentials).toBe("same-origin");
    expect(calls[1][1].cache).toBe("no-store");
    expect(calls[1][1].body).toBe(JSON.stringify({ username: "admin", password: "example" }));
  });
  it("uses authenticated CSRF headers for a single confirmed mutation", async () => {
    const f = fixture([response(200, { access_token: "access", token_type: "bearer" }), response(200, enabled)]);
    await settled();
    f.queue.push(response(200, enabled), response(200, { ...enabled, enabled: false }));
    f.get("disable").listeners.click();
    await settled();
    const calls = f.fetch.mock.calls as unknown as [string, RequestInit][];
    const mutation = calls.find(([path, options]) => path === "/api/v1/admin/maintenance" && options.method === "POST");
    expect(mutation?.[1].headers).toMatchObject({ Authorization: "Bearer access", "X-Atlas-Browser-Session": "1" });
    expect(mutation?.[1].body).toBe(JSON.stringify({ enabled: false }));
    expect(f.get("maintenance-status").textContent).toBe("Maintenance is off.");
  });
  it("never retries an uncertain mutation", async () => {
    const f = fixture([response(200, { access_token: "access", token_type: "bearer" }), response(200, enabled)]);
    await settled();
    f.queue.push(response(200, enabled), response(503));
    f.get("disable").listeners.click();
    await settled();
    const calls = f.fetch.mock.calls as unknown as [string, RequestInit][];
    expect(calls.filter(([path, options]) => path === "/api/v1/admin/maintenance" && options.method === "POST")).toHaveLength(1);
    expect(f.get("notice").textContent).toContain("not confirmed");
  });
  it("does not expose controls to a non-admin response", async () => {
    const f = fixture([response(200, { access_token: "ordinary", token_type: "bearer" }), response(403)]);
    await settled();
    expect(f.get("controls").hidden).toBe(true);
    expect(f.get("login").hidden).toBe(false);
  });
  it("signs out through browser revocation and removes in-memory access", async () => {
    const f = fixture([response(200, { access_token: "access", token_type: "bearer" }), response(200, enabled)]);
    await settled();
    f.queue.push(response(204));
    f.get("sign-out").listeners.click();
    await settled();
    expect(f.get("controls").hidden).toBe(true);
    expect(f.get("notice").textContent).toContain("Signed out");
  });
});
