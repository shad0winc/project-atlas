import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SettingsProfile } from "../api/settings";

import { SettingsProfileSurface } from "./SettingsView";

const profile: SettingsProfile = {
  user_id: "usr_123",
  username: "michael",
  display_name: "Michael",
  first_name: "Michael",
  last_name: "Atlas",
  email: "michael@example.com",
  discord_account: null,
  email_notifications_enabled: false,
  discord_notifications_enabled: false,
  roles: ["member"],
  provider: "jellyfin",
  granted_permission_patterns: ["users.self.read"],
  denied_permission_patterns: []
};

function renderSurface(
  canUpdate: boolean,
  discordAccount = ""
): string {
  return renderToStaticMarkup(
    <SettingsProfileSurface
      canUpdate={canUpdate}
      discordAccount={discordAccount}
      discordNotificationsEnabled={false}
      displayName="Michael"
      email="michael@example.com"
      emailNotificationsEnabled={false}
      firstName="Michael"
      lastName="Atlas"
      message={null}
      onDiscordAccountChange={() => undefined}
      onDiscordNotificationsChange={() => undefined}
      onDisplayNameChange={() => undefined}
      onEmailChange={() => undefined}
      onEmailNotificationsChange={() => undefined}
      onFirstNameChange={() => undefined}
      onLastNameChange={() => undefined}
      onSubmit={() => undefined}
      profile={profile}
      saving={false}
    />
  );
}

describe("SettingsProfileSurface", () => {
  it("renders editable self-service profile fields", () => {
    const markup = renderSurface(true);

    expect(markup).toContain("Display Name");
    expect(markup).toContain("Email Address");
    expect(markup).toContain("First Name");
    expect(markup).toContain("Last Name");
    expect(markup).toContain("Discord Account");
    expect(markup).toContain("Save profile");
    expect(markup).not.toContain("read-only access");
  });

  it("keeps privileged identity properties read-only", () => {
    const markup = renderSurface(true);

    expect(markup).toContain("Username");
    expect(markup).toContain("Authentication provider");
    expect(markup).toContain("Roles");
    expect(markup).not.toContain('name="roles"');
  });

  it("disables Discord notifications without an account", () => {
    const markup = renderSurface(true);

    expect(markup).toContain(
      "Add a Discord Account before enabling Discord notifications."
    );
    expect(markup).toContain('disabled=""');
  });

  it("renders read-only form controls when self-update is denied", () => {
    const markup = renderSurface(false, "atlas-user");

    expect(markup).toContain("read-only access");
    expect(markup).not.toContain("Save profile");
    expect(markup).toContain('disabled=""');
  });

  it("keeps required markers inline with their field labels", () => {
    const markup = renderSurface(true);

    expect(markup).toContain("Display Name");
    expect(markup).toContain("Email Address");
    expect(markup.match(/\*/g)?.length).toBeGreaterThanOrEqual(3);
  });
});
