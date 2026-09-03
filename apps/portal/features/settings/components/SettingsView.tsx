"use client";

import {
  type FormEvent,
  useCallback,
  useEffect,
  useState
} from "react";

import { Card } from "../../../components/ui/Card";
import {
  ATLAS_PERMISSIONS,
  usePermission
} from "../../../lib/authorization";

import {
  readSettingsProfile,
  type SettingsProfile,
  updateSettingsProfile
} from "../api/settings";

type LoadState = "loading" | "ready" | "error";

type SettingsProfileSurfaceProps = Readonly<{
  profile: SettingsProfile;
  displayName: string;
  firstName: string;
  lastName: string;
  email: string;
  discordAccount: string;
  emailNotificationsEnabled: boolean;
  discordNotificationsEnabled: boolean;
  canUpdate: boolean;
  saving: boolean;
  message: string | null;
  onDisplayNameChange: (value: string) => void;
  onFirstNameChange: (value: string) => void;
  onLastNameChange: (value: string) => void;
  onEmailChange: (value: string) => void;
  onDiscordAccountChange: (value: string) => void;
  onEmailNotificationsChange: (value: boolean) => void;
  onDiscordNotificationsChange: (value: boolean) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}>;

export function SettingsProfileSurface({
  profile,
  displayName,
  firstName,
  lastName,
  email,
  discordAccount,
  emailNotificationsEnabled,
  discordNotificationsEnabled,
  canUpdate,
  saving,
  message,
  onDisplayNameChange,
  onFirstNameChange,
  onLastNameChange,
  onEmailChange,
  onDiscordAccountChange,
  onEmailNotificationsChange,
  onDiscordNotificationsChange,
  onSubmit
}: SettingsProfileSurfaceProps): React.ReactElement {
  const discordAvailable = discordAccount.trim().length > 0;

  return (
    <div className="settings-grid">
      <Card className="settings-card">
        <div className="settings-card-heading">
          <div>
            <p className="portal-page-eyebrow">Account</p>
            <h3>Identity</h3>
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
            <dd>
              {profile.roles.length
                ? profile.roles.join(", ")
                : "None"}
            </dd>
          </div>
        </dl>

        <p className="settings-boundary-note">
          Your username, authentication provider, and access roles are
          managed by Atlas administration.
        </p>
      </Card>

      <Card className="settings-card settings-profile-card">
        <p className="portal-page-eyebrow">Profile</p>
        <h3>Profile &amp; notifications</h3>

        <p>
          Manage the profile information and notification preferences
          associated with your Atlas account.
        </p>

        <form className="settings-form" onSubmit={onSubmit}>
          <div className="settings-field-grid">
            <label className="settings-field">
              <span>
                Display Name <span aria-hidden="true">*</span>
              </span>

              <input
                autoComplete="name"
                disabled={!canUpdate || saving}
                maxLength={100}
                onChange={(event) =>
                  onDisplayNameChange(event.target.value)
                }
                required
                type="text"
                value={displayName}
              />
            </label>

            <label className="settings-field">
              <span>
                Email Address <span aria-hidden="true">*</span>
              </span>

              <input
                autoComplete="email"
                disabled={!canUpdate || saving}
                maxLength={320}
                onChange={(event) =>
                  onEmailChange(event.target.value)
                }
                required
                type="email"
                value={email}
              />
            </label>

            <label className="settings-field">
              <span>First Name</span>

              <input
                autoComplete="given-name"
                disabled={!canUpdate || saving}
                maxLength={100}
                onChange={(event) =>
                  onFirstNameChange(event.target.value)
                }
                type="text"
                value={firstName}
              />
            </label>

            <label className="settings-field">
              <span>Last Name</span>

              <input
                autoComplete="family-name"
                disabled={!canUpdate || saving}
                maxLength={100}
                onChange={(event) =>
                  onLastNameChange(event.target.value)
                }
                type="text"
                value={lastName}
              />
            </label>

            <label className="settings-field settings-field--wide">
              <span>Discord Account</span>

              <input
                autoComplete="off"
                disabled={!canUpdate || saving}
                maxLength={200}
                onChange={(event) =>
                  onDiscordAccountChange(event.target.value)
                }
                type="text"
                value={discordAccount}
              />
            </label>
          </div>

          <fieldset
            className="settings-notifications"
            disabled={!canUpdate || saving}
          >
            <legend>Notifications</legend>

            <label className="settings-checkbox-row">
              <input
                checked={emailNotificationsEnabled}
                onChange={(event) =>
                  onEmailNotificationsChange(event.target.checked)
                }
                type="checkbox"
              />

              <span>Email notifications</span>
            </label>

            <label className="settings-checkbox-row">
              <input
                checked={discordNotificationsEnabled}
                disabled={
                  !canUpdate ||
                  saving ||
                  !discordAvailable
                }
                onChange={(event) =>
                  onDiscordNotificationsChange(event.target.checked)
                }
                type="checkbox"
              />

              <span>Discord notifications</span>
            </label>

            {!discordAvailable ? (
              <p className="settings-boundary-note">
                Add a Discord Account before enabling Discord
                notifications.
              </p>
            ) : null}
          </fieldset>

          <p className="settings-required-note">
            Fields marked with{" "}
            <span aria-hidden="true">*</span> are required.
          </p>

          {!canUpdate ? (
            <p className="settings-boundary-note">
              Your Atlas account has read-only access to these settings.
            </p>
          ) : null}

          {message ? (
            <p aria-live="polite">{message}</p>
          ) : null}

          {canUpdate ? (
            <button
              className="button button--primary"
              disabled={saving}
              type="submit"
            >
              {saving ? "Saving…" : "Save profile"}
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

  const [profile, setProfile] =
    useState<SettingsProfile | null>(null);

  const [displayName, setDisplayName] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [discordAccount, setDiscordAccount] = useState("");
  const [
    emailNotificationsEnabled,
    setEmailNotificationsEnabled
  ] = useState(false);
  const [
    discordNotificationsEnabled,
    setDiscordNotificationsEnabled
  ] = useState(false);

  const [loadState, setLoadState] =
    useState<LoadState>("loading");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] =
    useState<string | null>(null);
  const [requestVersion, setRequestVersion] = useState(0);

  const reload = useCallback((): void => {
    setLoadState("loading");
    setMessage(null);
    setRequestVersion((current) => current + 1);
  }, []);

  function applyProfile(currentProfile: SettingsProfile): void {
    setProfile(currentProfile);
    setDisplayName(currentProfile.display_name);
    setFirstName(currentProfile.first_name ?? "");
    setLastName(currentProfile.last_name ?? "");
    setEmail(currentProfile.email ?? "");
    setDiscordAccount(currentProfile.discord_account ?? "");
    setEmailNotificationsEnabled(
      currentProfile.email_notifications_enabled
    );
    setDiscordNotificationsEnabled(
      currentProfile.discord_notifications_enabled
    );
  }

  useEffect(() => {
    let active = true;

    void readSettingsProfile()
      .then((currentProfile) => {
        if (!active) {
          return;
        }

        applyProfile(currentProfile);
        setLoadState("ready");
      })
      .catch(() => {
        if (!active) {
          return;
        }

        setProfile(null);
        setLoadState("error");
        setMessage(
          "Atlas could not load your account settings."
        );
      });

    return () => {
      active = false;
    };
  }, [requestVersion]);

  async function onSubmit(
    event: FormEvent<HTMLFormElement>
  ): Promise<void> {
    event.preventDefault();

    if (!canUpdate || saving) {
      return;
    }

    if (!displayName.trim()) {
      setMessage("Display name cannot be empty.");
      return;
    }

    if (!email.trim()) {
      setMessage("Email address cannot be empty.");
      return;
    }

    if (
      discordNotificationsEnabled &&
      !discordAccount.trim()
    ) {
      setMessage(
        "Add a Discord account before enabling Discord notifications."
      );
      return;
    }

    setSaving(true);
    setMessage(null);

    try {
      const updated = await updateSettingsProfile({
        displayName,
        firstName,
        lastName,
        email,
        discordAccount,
        emailNotificationsEnabled,
        discordNotificationsEnabled
      });

      applyProfile(updated);
      setMessage("Profile saved.");
    } catch {
      setMessage("Atlas could not save your profile.");
    } finally {
      setSaving(false);
    }
  }

  if (loadState === "loading") {
    return (
      <Card className="settings-card">
        <p aria-live="polite">
          Loading account settings…
        </p>
      </Card>
    );
  }

  if (loadState === "error" || profile === null) {
    return (
      <Card className="settings-card">
        <h3>Account settings unavailable</h3>

        <p role="alert">
          {message ??
            "Atlas could not load your account settings."}
        </p>

        <button
          className="button button--secondary"
          onClick={reload}
          type="button"
        >
          Try again
        </button>
      </Card>
    );
  }

  return (
    <SettingsProfileSurface
      canUpdate={canUpdate}
      discordAccount={discordAccount}
      discordNotificationsEnabled={
        discordNotificationsEnabled
      }
      displayName={displayName}
      email={email}
      emailNotificationsEnabled={
        emailNotificationsEnabled
      }
      firstName={firstName}
      lastName={lastName}
      message={message}
      onDiscordAccountChange={(value) => {
        setDiscordAccount(value);

        if (!value.trim()) {
          setDiscordNotificationsEnabled(false);
        }
      }}
      onDiscordNotificationsChange={
        setDiscordNotificationsEnabled
      }
      onDisplayNameChange={setDisplayName}
      onEmailChange={setEmail}
      onEmailNotificationsChange={
        setEmailNotificationsEnabled
      }
      onFirstNameChange={setFirstName}
      onLastNameChange={setLastName}
      onSubmit={onSubmit}
      profile={profile}
      saving={saving}
    />
  );
}
