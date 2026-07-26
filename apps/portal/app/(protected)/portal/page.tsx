"use client";

import { useAuth } from "../../../lib/auth/use-auth";

export default function PortalPage(): React.ReactElement {
  const { user } = useAuth();

  const displayName = user?.display_name.trim() || user?.username.trim() || "Atlas user";

  return (
    <div className="portal-page">
      <header className="portal-page-header">
        <div>
          <p className="portal-page-eyebrow">Dashboard</p>
          <h2 className="portal-page-title">Welcome back, {displayName}</h2>
          <p className="portal-page-description">
            Review the current state of your Project Atlas environment.
          </p>
        </div>
      </header>

      <section aria-label="Dashboard overview" className="portal-dashboard-grid">
        <article className="portal-dashboard-card">
          <p className="portal-dashboard-card-label">System health</p>
          <strong className="portal-dashboard-card-value">Preparing</strong>
          <p className="portal-dashboard-card-description">
            Live Atlas health data will be connected in the next dashboard slice.
          </p>
        </article>

        <article className="portal-dashboard-card">
          <p className="portal-dashboard-card-label">Media libraries</p>
          <strong className="portal-dashboard-card-value">Preparing</strong>
          <p className="portal-dashboard-card-description">
            Library statistics will appear here after the media service integration.
          </p>
        </article>

        <article className="portal-dashboard-card">
          <p className="portal-dashboard-card-label">Storage</p>
          <strong className="portal-dashboard-card-value">Preparing</strong>
          <p className="portal-dashboard-card-description">
            Storage capacity and usage will be sourced from Atlas ARI.
          </p>
        </article>

        <article className="portal-dashboard-card">
          <p className="portal-dashboard-card-label">Requests</p>
          <strong className="portal-dashboard-card-value">Preparing</strong>
          <p className="portal-dashboard-card-description">
            Pending and recent media requests will appear in this panel.
          </p>
        </article>
      </section>
    </div>
  );
}
