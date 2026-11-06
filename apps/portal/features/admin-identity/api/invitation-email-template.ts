import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export const invitationTextFields = [
  "subject",
  "heading",
  "welcome",
  "instructions",
  "button_label"
] as const;
export type InvitationTextField = (typeof invitationTextFields)[number];
export type InvitationEmailTemplate = Readonly<Record<InvitationTextField, string>>;
export type InvitationEmailDocument = Readonly<{
  template: InvitationEmailTemplate;
  defaults: InvitationEmailTemplate;
  limits: Readonly<Record<InvitationTextField, number>>;
}>;

function document(value: InvitationEmailDocument): InvitationEmailDocument {
  if (
    !value ||
    invitationTextFields.some(
      (field) =>
        typeof value.template?.[field] !== "string" ||
        typeof value.defaults?.[field] !== "string" ||
        !Number.isInteger(value.limits?.[field]) ||
        value.limits[field] < 1 ||
        value.limits[field] > 2000
    )
  ) {
    throw new Error("Atlas returned invalid invitation email settings.");
  }
  return value;
}

export async function loadInvitationEmailTemplate(
  signal?: AbortSignal
): Promise<InvitationEmailDocument> {
  return document(
    await authenticatedAtlasApiRequest<InvitationEmailDocument>(
      "/admin/invitations/email-template",
      { method: "GET", cache: "no-store", signal }
    )
  );
}

export async function saveInvitationEmailTemplate(
  template: InvitationEmailTemplate
): Promise<InvitationEmailDocument> {
  return document(
    await authenticatedAtlasApiRequest<InvitationEmailDocument>(
      "/admin/invitations/email-template",
      {
        method: "PUT",
        cache: "no-store",
        body: { template },
        retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5000 }
      }
    )
  );
}
