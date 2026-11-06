// @vitest-environment happy-dom
import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { InvitationEmailDocument } from "../api/invitation-email-template";
import { InvitationEmailEditor, InvitationEmailPreview } from "./InvitationEmailEditor";

const mocks = vi.hoisted(() => ({ load: vi.fn(), save: vi.fn() }));
vi.mock("../api/invitation-email-template", async (original) => ({
  ...(await original<typeof import("../api/invitation-email-template")>()),
  loadInvitationEmailTemplate: mocks.load,
  saveInvitationEmailTemplate: mocks.save
}));
const defaults = {
  subject: "Join Atlas",
  heading: "Welcome!",
  welcome: "All things media.",
  instructions: "Create your account.",
  button_label: "Accept invitation"
};
const loaded: InvitationEmailDocument = {
  template: { ...defaults, heading: "Saved custom heading" },
  defaults,
  limits: { subject: 160, heading: 100, welcome: 1200, instructions: 500, button_label: 40 }
};
let root: Root, container: HTMLDivElement;
beforeEach(() => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  mocks.load.mockReset().mockResolvedValue(loaded);
  mocks.save.mockReset().mockResolvedValue({ ...loaded, template: defaults });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
});
async function mountAndOpen() {
  await act(async () => root.render(<InvitationEmailEditor />));
  expect(mocks.load).not.toHaveBeenCalled();
  await act(async () => (container.querySelector("button") as HTMLButtonElement).click());
}
function button(label: string): HTMLButtonElement {
  const found = [...container.querySelectorAll("button")].find(
    (item) => item.textContent === label
  );
  if (!found) throw new Error(`Missing ${label}`);
  return found;
}
it("loads saved fields and previews the existing copy without sending mail", async () => {
  await mountAndOpen();
  expect((container.querySelector("#invitation-template-heading") as HTMLInputElement).value).toBe(
    "Saved custom heading"
  );
  expect(
    container.querySelector('[aria-label="Invitation email text preview"]')?.textContent
  ).toContain("Saved custom heading");
  expect(button("Save email template").disabled).toBe(true);
  expect(mocks.save).not.toHaveBeenCalled();
});
it("reset changes only the draft; Save persists it and confirms future email use", async () => {
  await mountAndOpen();
  await act(async () => button("Reset draft to defaults").click());
  expect(mocks.save).not.toHaveBeenCalled();
  expect(container.textContent).toContain("Defaults loaded. Save to apply.");
  expect(button("Save email template").disabled).toBe(false);
  await act(async () => {
    container
      .querySelector("form")!
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  expect(mocks.save).toHaveBeenCalledExactlyOnceWith(defaults);
  expect(container.textContent).toContain("New invitations will use this text.");
  expect(button("Save email template").disabled).toBe(true);
});
it("failed saves keep the draft available for retry", async () => {
  mocks.save.mockRejectedValue(new Error("Writer unavailable"));
  await mountAndOpen();
  await act(async () => button("Reset draft to defaults").click());
  await act(async () => {
    container
      .querySelector("form")!
      .dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
  });
  expect(container.querySelector('[role="alert"]')?.textContent).toBe("Writer unavailable");
  expect((container.querySelector("#invitation-template-heading") as HTMLInputElement).value).toBe(
    defaults.heading
  );
  expect(button("Save email template").disabled).toBe(false);
});
it("escapes preview text and does not create registration links or execute markup", () => {
  const html = renderToStaticMarkup(
    <InvitationEmailPreview template={{ ...defaults, heading: "<script>alert(1)</script>" }} />
  );
  expect(html).toContain("&lt;script&gt;");
  expect(html).not.toContain("<script>");
  expect(html).not.toContain("href=");
});
