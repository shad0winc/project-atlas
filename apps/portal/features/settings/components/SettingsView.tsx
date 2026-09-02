"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { Card } from "../../../components/ui/Card";
import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";

import {
  readSettingsProfile,
  type SettingsProfile,
  updateSettingsDisplayName
} from "../api/settings";

type LoadState = "loading" | "ready" | "error";

type SettingsProfileSurfaceProps = Readonly<{
  profile: SettingsProfile;
  displayName: string;
  canUpdate: boolean;
  saving: boolean;
  message: string | null;
  onDisplayNameChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}>;

export function SettingsProfileSurface({
  profile,
  displayName,
  canUpdate,
  saving,
  message,
  onDisplayNameChange,
  onSubmit
}: SettingsProfileSurfaceProps): React.ReactElement {
  return (
    <div className="settings-grid">
      <Card className="settings-card">
        <div className="settings-card-heading">
          <div>
            <p className="portal-page-eyebrow">Account</p>
            <h3>Profile</h3>
          </div>
          <span className="settings-provider">{profile.provider}</span>
        </div>

        <dl className="settings-account-details">
          <div>
            <dt>Username</dt>
            <dd>{profile.username}</dd>
          </div>
          <div>
            <dt>Authentication provider</dt>
            <dd>{profile.provider}</dd>
          </div>
          <div>
            <dt>Roles</dt>
            <dd>{profile.roles.length ? profile.roles.join(", ") : "None"}</dd>
          </div>
        </dl>

        <p className="settings-boundary-note">
          Your username and sign-in identity are managed by the authentication provider.
        </p>
      </Card>

      <Card className="settings-card">
        <p className="portal-page-eyebrow">Personalization</p>
        <h3>Display name</h3>
        <p>Choose the name Atlas uses on supported Portal account surfaces.</p>

        <form className="settings-form" onSubmit={onSubmit}>
          <label className="settings-field">
            <span>Display name</span>
            <input
              autoComplete="name"
              disabled={!canUpdate || saving}
              maxLength={100}
              onChange={(event) => onDisplayNameChange(event.target.value)}
              required
              type="text"
              value={displayName}
            />
          </label>

          {!canUpdate ? (
            <p className="settings-boundary-note">
              Your Atlas account has read-only access to these settings.
            </p>
          ) : null}

          {message ? <p aria-live="polite">{message}</p> : null}

          {canUpdate ? (
            <button className="button button--primary" disabled={saving} type="submit">
              {saving ? "Saving…" : "Save display name"}
            </button>
          ) : null}
        </form>
      </Card>
    </div>
  );
}

export function SettingsView(): React.ReactElement {
  const { can } = usePermission();
  const canUpdate = can(ATLAS_PERMISSIONS.usersSelfUpdate);
  const [profile, setProfile] = useState<SettingsProfile | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  const reload = useCallback((): void => {
    setLoadState("loading");
    setMessage(null);
    setRequestVersion((current) => current + 1);
  }, []);

  useEffect(() => {
    let active = true;

    void readSettingsProfile()
      .then((currentProfile) => {
        if (!active) {
          return;
        }

        setProfile(currentProfile);
        setDisplayName(currentProfile.display_name);
        setLoadState("ready");
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setProfile(null);
        setLoadState("error");
        setMessage("Atlas could not load your account settings.");
      });

    return () => {
      active = false;
    };
  }, [requestVersion]);

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();

    if (!canUpdate || saving) {
      return;
    }

    const normalizedDisplayName = displayName.trim();

    if (!normalizedDisplayName) {
      setMessage("Display name cannot be empty.");
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const updated = await updateSettingsDisplayName(normalizedDisplayName);
      setProfile(updated);
      setDisplayName(updated.display_name);
      setMessage("Display name saved.");
    } catch {
      setMessage("Atlas could not save your display name.");
    } finally {
      setSaving(false);
    }
  }

  if (loadState === "loading") {
    return (
      <Card className="settings-card">
        <p aria-live="polite">Loading account settings…</p>
      </Card>
    );
  }

  if (loadState === "error" || profile === null) {
    return (
      <Card className="settings-card">
        <h3>Account settings unavailable</h3>
        <p role="alert">{message ?? "Atlas could not load your account settings."}</p>
        <button className="button button--secondary" onClick={reload} type="button">
          Try again
        </button>
      </Card>
    );
  }

  return (
    <SettingsProfileSurface
      canUpdate={canUpdate}
      displayName={displayName}
      message={message}
      onDisplayNameChange={setDisplayName}
      onSubmit={onSubmit}
      profile={profile}
      saving={saving}
    />
  );
}
