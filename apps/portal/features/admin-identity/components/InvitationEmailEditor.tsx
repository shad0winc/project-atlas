"use client";

import { useEffect, useState } from "react";
import {
  invitationTextFields,
  loadInvitationEmailTemplate,
  saveInvitationEmailTemplate,
  type InvitationEmailDocument,
  type InvitationEmailTemplate,
  type InvitationTextField
} from "../api/invitation-email-template";

const labels: Record<InvitationTextField, string> = {
  subject: "Subject",
  heading: "Heading",
  welcome: "Welcome message",
  instructions: "Instructions",
  button_label: "Button label"
};

export function InvitationEmailPreview({
  template
}: Readonly<{ template: InvitationEmailTemplate }>): React.ReactElement {
  return (
    <section
      aria-label="Invitation email text preview"
      className="card"
      style={{ background: "#121b2e", color: "#eaf0ff", padding: "1.5rem" }}
    >
      <p>Subject: {template.subject}</p>
      <p className="portal-page-eyebrow">Project Atlas</p>
      <h4>{template.heading}</h4>
      <p style={{ whiteSpace: "pre-wrap" }}>{template.welcome}</p>
      <p style={{ whiteSpace: "pre-wrap" }}>{template.instructions}</p>
      <span
        style={{
          display: "inline-block",
          background: "#75c9ff",
          color: "#000",
          fontWeight: "bold",
          padding: "0.75rem 1rem",
          borderRadius: "8px"
        }}
      >
        {template.button_label}
      </span>
      <p>Atlas adds the panda image, secure registration link, and expiry when sending.</p>
    </section>
  );
}

function InvitationEmailForm(): React.ReactElement {
  const [document, setDocument] = useState<InvitationEmailDocument | null>(null);
  const [draft, setDraft] = useState<InvitationEmailTemplate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [requestId, setRequestId] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    loadInvitationEmailTemplate(controller.signal)
      .then((loaded) => {
        if (!controller.signal.aborted) {
          setDocument(loaded);
          setDraft(loaded.template);
        }
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setError(
            failure instanceof Error ? failure.message : "Unable to load invitation email settings."
          );
      });
    return () => controller.abort();
  }, [requestId]);

  if (!document || !draft) {
    return error ? (
      <div role="alert">
        <p>{error}</p>
        <button
          type="button"
          onClick={() => {
            setError(null);
            setRequestId((value) => value + 1);
          }}
        >
          Retry email settings
        </button>
      </div>
    ) : (
      <p role="status">Loading invitation email settings…</p>
    );
  }
  const changed = invitationTextFields.some((field) => draft[field] !== document.template[field]);
  const valid = invitationTextFields.every(
    (field) => draft[field].trim() && draft[field].length <= document.limits[field]
  );

  async function save(): Promise<void> {
    if (!draft) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await saveInvitationEmailTemplate(draft);
      setDocument(saved);
      setDraft(saved.template);
      setNotice("Invitation email saved. New invitations will use this text.");
    } catch (failure: unknown) {
      setError(
        failure instanceof Error ? failure.message : "Unable to save invitation email settings."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      aria-label="Invitation email settings"
      aria-busy={busy}
      onSubmit={(event) => {
        event.preventDefault();
        void save();
      }}
      style={{ display: "grid", gap: "1rem" }}
    >
      <p>Changes apply to new invitation emails. Already sent emails stay the same.</p>
      {invitationTextFields.map((field) => (
        <label
          key={field}
          htmlFor={`invitation-template-${field}`}
          style={{ display: "grid", gap: "0.35rem" }}
        >
          {labels[field]}
          {field === "welcome" || field === "instructions" ? (
            <textarea
              id={`invitation-template-${field}`}
              value={draft[field]}
              required
              maxLength={document.limits[field]}
              rows={4}
              disabled={busy}
              onChange={(event) => {
                setDraft({ ...draft, [field]: event.target.value });
                setNotice(null);
              }}
            />
          ) : (
            <input
              id={`invitation-template-${field}`}
              value={draft[field]}
              required
              maxLength={document.limits[field]}
              disabled={busy}
              onChange={(event) => {
                setDraft({ ...draft, [field]: event.target.value });
                setNotice(null);
              }}
            />
          )}
        </label>
      ))}
      {error ? <p role="alert">{error}</p> : null}
      {notice ? <p role="status">{notice}</p> : null}
      {changed ? <p>Unsaved changes</p> : null}
      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
        <button type="submit" disabled={busy || !changed || !valid}>
          {busy ? "Saving…" : "Save email template"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => {
            setDraft({ ...document.defaults });
            setNotice("Defaults loaded. Save to apply.");
            setError(null);
          }}
        >
          Reset draft to defaults
        </button>
      </div>
      <InvitationEmailPreview template={draft} />
    </form>
  );
}

export function InvitationEmailEditor(): React.ReactElement {
  const [open, setOpen] = useState(false);
  return (
    <section className="card admin-identity-card" aria-labelledby="invitation-email-title">
      <h4 id="invitation-email-title">Invitation email</h4>
      <button type="button" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        {open ? "Close email editor" : "Customize invitation email"}
      </button>
      {open ? <InvitationEmailForm /> : null}
    </section>
  );
}
