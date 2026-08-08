"use client";

import type { ReactNode } from "react";

import { RequirePermission } from "../auth/RequirePermission";
import type { AtlasPermission } from "../../lib/authorization";

import { PortalAccessDenied } from "./PortalAccessDenied";

export type PortalPageProps = Readonly<{
  permission: AtlasPermission;
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  accessDeniedTitle?: string;
  accessDeniedDescription?: string;
  accessDeniedGuidance?: ReactNode;
}>;

/**
 * Canonical authorization and presentation boundary for protected Portal pages.
 *
 * Authentication is owned by the protected App Router layout. This component
 * applies API-resolved effective permissions to presentation only; protected
 * API requests remain independently enforced by the Atlas API.
 */
export function PortalPage({
  permission,
  eyebrow,
  title,
  description,
  actions,
  children,
  accessDeniedTitle,
  accessDeniedDescription,
  accessDeniedGuidance
}: PortalPageProps): React.ReactElement {
  return (
    <RequirePermission
      fallback={
        <div className="portal-page">
          <PortalAccessDenied
            description={accessDeniedDescription}
            guidance={accessDeniedGuidance}
            title={accessDeniedTitle}
          />
        </div>
      }
      permission={permission}
    >
      <div className="portal-page">
        <header className="portal-page-header">
          <div className="portal-page-heading">
            <p className="portal-page-eyebrow">{eyebrow}</p>

            <h2 className="portal-page-title">{title}</h2>

            {description ? <div className="portal-page-description">{description}</div> : null}
          </div>

          {actions ? <div className="portal-page-actions">{actions}</div> : null}
        </header>

        <div className="portal-page-body">{children}</div>
      </div>
    </RequirePermission>
  );
}
