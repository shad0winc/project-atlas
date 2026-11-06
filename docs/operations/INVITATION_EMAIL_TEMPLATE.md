# Invitation email copy

The **Invitations** panel appears directly on **Administration** for users with
`users.read`. It also remains under **Users and access → Invitations**.
Users with `users.update` can open
**Customize invitation email**. Edit the subject, heading, welcome message,
instructions and button label. The preview shows the editable text; Atlas adds
the panda artwork, registration links and expiry when sending.

**Save email template** applies the text to future invitation emails. Sent emails
remain unchanged. **Reset draft to defaults** loads the defaults into the editor;
save to apply them. A failed save keeps the draft available for retry.

## Invitation history

**Current** is the default invitation view. Completed (accepted) and revoked
invitations move to **Archived** once 24 hours have passed since `completed_at`
or `revoked_at`, respectively. Existing records already past that boundary appear
in Archived immediately. Creation time is never used as the archive clock.
Pending invitations and records without valid terminal timestamps stay visible
in Current. This view does not change token validity, expiry, lifecycle status,
the registry or retained record files; nothing is deleted.

The page reevaluates the cutoff every minute and on focus. Invitation status is
refreshed in the background every minute while the page is visible and no identity
mutation is in progress, and when the window regains focus. Background refresh
preserves open forms and email drafts. Failed refreshes preserve the current data
and display a retry message. **Refresh invitations** performs an explicit reload.
The archive can be inspected at any time using the **Archived** button and count.

This history/navigation change requires only a Portal image update. The existing
API already returns lifecycle timestamps, and completed/revoked records are
already retained in the invitation store. No migration or scheduler job is needed.

These are plain-text fields, not HTML or template code. HTML output is escaped.
The secure registration URL, token, expiry, SMTP sender, artwork and styles remain
application-controlled. Subject/header controls and empty or overlong values are
rejected by both the public API and the private identity writer.

| Field | Maximum characters |
| --- | ---: |
| Subject | 160 |
| Heading | 100 |
| Welcome message | 1200 |
| Instructions | 500 |
| Button label | 40 |

## Storage and deployment

The identity writer atomically saves a versioned JSON document at
`$ATLAS_IDENTITY_DIR/invitations/email-template.json` (normally under
`/mnt/storage/configs/atlas/identity`). The API reads this through its existing
read-only invitation mount. No additional writable mount is required, and these
operations do not initialize password-recovery storage or modify invitation
tokens/records. Missing settings use the built-in defaults without writing files.
Malformed stored settings cause an explicit error rather than silently replacing
the saved text. Include this file in identity backups.

Deploy the shared `atlas.invitation_email_template` module to the API and identity
writer, the writer endpoint/client/public routes and mail changes, and the Portal
editor together. The API's template GET/PUT endpoints require `users.update`; the
private PUT endpoint also requires the identity-writer service token. A mutation
is not automatically retried by the Portal.

Rolling back to an older application leaves the saved JSON intact. Older email
code uses its built-in copy until the template-aware version is restored.
