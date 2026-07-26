"use client";

import { useAuth } from "../../../lib/auth/use-auth";

export default function PortalPage(): React.ReactElement {
  const { user } = useAuth();

  const displayName = user?.display_name.trim() || user?.username.trim() || "Atlas user";

  return (
    <main className="auth-page">
      <section aria-labelledby="atlas-portal-heading" className="auth-panel">
        <p className="auth-eyebrow">Private Portal</p>

        <h1 className="auth-title" id="atlas-portal-heading">
          Welcome, {displayName}
        </h1>

        <p className="auth-description">Your authenticated Project Atlas session is active.</p>

        <dl className="auth-session-details">
          <div>
            <dt>Username</dt>
            <dd>{user?.username ?? "Unavailable"}</dd>
          </div>

          <div>
            <dt>Identity provider</dt>
            <dd>{user?.provider ?? "Unavailable"}</dd>
          </div>

          <div>
            <dt>Roles</dt>
            <dd>{user?.roles.length ? user.roles.join(", ") : "No assigned roles"}</dd>
          </div>
        </dl>
      </section>
    </main>
  );
}
