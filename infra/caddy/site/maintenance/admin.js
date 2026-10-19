"use strict";
(() => {
  const element = (id) => document.getElementById(id);
  const form = element("login");
  const controls = element("controls");
  const notice = element("notice");
  let access = null;
  let busy = false;

  function signedOut(message) {
    access = null;
    form.hidden = false;
    controls.hidden = true;
    notice.textContent = message;
  }

  async function request(path, method = "GET", body, authenticated = false) {
    const headers = { "X-Atlas-Browser-Session": "1" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (authenticated && access) headers.Authorization = "Bearer " + access;
    const response = await fetch(path, {
      method, headers, credentials: "same-origin", cache: "no-store",
      ...(body === undefined ? {} : { body: JSON.stringify(body) })
    });
    if (!response.ok) {
      const error = new Error("Administrator access or maintenance control is unavailable.");
      error.status = response.status;
      throw error;
    }
    return response.status === 204 ? null : response.json();
  }

  async function browser(action, credentials) {
    if (!navigator.locks) throw new Error("This browser cannot coordinate secure Atlas sessions.");
    return navigator.locks.request("atlas-browser-session", () =>
      request("/api/v1/auth/browser/" + action, "POST", credentials));
  }

  function receiveSession(result) {
    if (!result || typeof result.access_token !== "string" || !result.access_token || result.token_type !== "bearer") {
      throw new Error("Administrator session could not be established.");
    }
    access = result.access_token;
  }

  function show(state) {
    if (!state || ["enabled", "recovery_held", "transition_pending", "state_uncertain"].some((key) => typeof state[key] !== "boolean")) {
      throw new Error("Maintenance status could not be confirmed.");
    }
    form.hidden = true;
    controls.hidden = false;
    element("maintenance-status").textContent = "Maintenance is " + (state.enabled ? "on." : "off.");
    const held = state.recovery_held || state.transition_pending || state.state_uncertain;
    element("recovery-status").textContent = held
      ? "A recovery or operation hold is active. Maintenance cannot be turned off."
      : "No recovery hold is active.";
    element("disable").disabled = held || !state.enabled;
    element("enable").disabled = state.enabled || state.transition_pending || state.state_uncertain;
    notice.textContent = "Administrator session active.";
  }

  async function refreshStatus(rotate = true) {
    try {
      show(await request("/api/v1/admin/maintenance", "GET", undefined, true));
    } catch (error) {
      if (!rotate || ![401, 503].includes(error.status)) throw error;
      receiveSession(await browser("refresh"));
      show(await request("/api/v1/admin/maintenance", "GET", undefined, true));
    }
  }

  async function act(task) {
    if (busy) return;
    busy = true;
    element("sign-in").disabled = true;
    try { await task(); }
    catch (error) { notice.textContent = error.message || "The operation was not confirmed. Refresh status before trying again."; }
    finally { busy = false; element("sign-in").disabled = false; }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    void act(async () => {
      try {
        receiveSession(await browser("login", { username: element("username").value.trim(), password: element("password").value }));
        await refreshStatus(false);
      } catch (error) {
        signedOut("Administrator sign-in was not confirmed. Check your account and try again.");
        throw error;
      } finally { element("password").value = ""; }
    });
  });

  async function change(enabled) {
    await refreshStatus();
    if (element(enabled ? "enable" : "disable").disabled) return;
    try {
      show(await request("/api/v1/admin/maintenance", "POST", { enabled }, true));
    } catch (error) {
      notice.textContent = "State change was not confirmed. Refresh status before trying again.";
      // Never automatically retry a mutation with an uncertain outcome.
      throw new Error(notice.textContent);
    }
  }
  element("enable").addEventListener("click", () => { void act(() => change(true)); });
  element("disable").addEventListener("click", () => { void act(() => change(false)); });
  element("refresh").addEventListener("click", () => { void act(() => refreshStatus()); });
  element("sign-out").addEventListener("click", () => { void act(async () => {
    await browser("logout");
    signedOut("Signed out. Administrator access is required.");
  }); });

  void act(async () => {
    try { receiveSession(await browser("refresh")); await refreshStatus(false); }
    catch { signedOut("Administrator access is required. Sign in to continue."); }
  });
})();
