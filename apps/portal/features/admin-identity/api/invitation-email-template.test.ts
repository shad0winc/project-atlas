import { describe, expect, it, vi } from "vitest";
import {
  loadInvitationEmailTemplate,
  saveInvitationEmailTemplate
} from "./invitation-email-template";

const request = vi.hoisted(() => vi.fn());
vi.mock("../../../lib/services/authenticated", () => ({ authenticatedAtlasApiRequest: request }));
const template = {
  subject: "Join",
  heading: "Hi",
  welcome: "Welcome",
  instructions: "Join us",
  button_label: "Accept"
};
const response = {
  template,
  defaults: template,
  limits: { subject: 160, heading: 100, welcome: 1200, instructions: 500, button_label: 40 }
};
describe("invitation email template transport", () => {
  it("uses authenticated no-store reads and sends only text fields on save", async () => {
    request.mockResolvedValue(response);
    await loadInvitationEmailTemplate();
    expect(request).toHaveBeenCalledWith(
      "/admin/invitations/email-template",
      expect.objectContaining({ method: "GET", cache: "no-store" })
    );
    await saveInvitationEmailTemplate(template);
    expect(request).toHaveBeenLastCalledWith(
      "/admin/invitations/email-template",
      expect.objectContaining({
        method: "PUT",
        body: { template },
        retryPolicy: expect.objectContaining({ maxRetries: 0 })
      })
    );
  });
  it("rejects malformed responses instead of replacing the editor with undefined values", async () => {
    request.mockResolvedValue({ template: {} });
    await expect(loadInvitationEmailTemplate()).rejects.toThrow(
      "invalid invitation email settings"
    );
  });
});
