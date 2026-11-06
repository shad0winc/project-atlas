# Invitation email copy

In **Administration → Invitations**, users with `users.update` can open
**Customize invitation email**. Edit the subject, heading, welcome message,
instructions and button label. The preview shows the editable text; Atlas adds
the panda artwork, registration links and expiry when sending.

**Save email template** applies the text to future invitation emails. Sent emails
remain unchanged. **Reset draft to defaults** loads the defaults into the editor;
save to apply them. A failed save keeps the draft available for retry.

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
