import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SettingsProfile } from "../api/settings";

import { SettingsProfileSurface } from "./SettingsView";

const profile: SettingsProfile = {
  user_id: "usr_123",
  username: "michael",
  display_name: "Michael",
  roles: ["member"],
  provider: "jellyfin",
  granted_permission_patterns: ["users.self.read"],
  denied_permission_patterns: []
};

function renderSurface(canUpdate: boolean): string {
  return renderToStaticMarkup(
    <SettingsProfileSurface
      canUpdate={canUpdate}
      displayName="Michael"
      message={null}
      onDisplayNameChange={() => undefined}
      onSubmit={() => undefined}
      profile={profile}
      saving={false}
    />
  );
}

describe("SettingsProfileSurface", () => {
  it("renders an editable display-name action when self-update is allowed", () => {
    const markup = renderSurface(true);

    expect(markup).toContain("Save display name");
    expect(markup).not.toContain("read-only access");
    expect(markup).not.toContain('disabled=""');
  });

  it("renders a read-only display-name surface when self-update is denied", () => {
    const markup = renderSurface(false);

    expect(markup).toContain("read-only access");
    expect(markup).not.toContain("Save display name");
    expect(markup).toContain('disabled=""');
  });
});
