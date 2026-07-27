import type { ReactNode } from "react";

export type PortalAccessDeniedProps = Readonly<{
  title?: string;
  description?: string;
  guidance?: ReactNode;
}>;

/**
 * Standard presentation shown when an authenticated Portal user lacks the
 * effective permission required by a page.
 *
 * API authorization remains the authoritative security boundary.
 */
export function PortalAccessDenied({
  title = "Access unavailable",
  description = "Your Atlas account does not have permission to access this section.",
  guidance = "If you believe this is incorrect, contact your Atlas administrator."
}: PortalAccessDeniedProps): React.ReactElement {
  return (
    <section
      aria-labelledby="portal-access-denied-title"
      className="portal-access-denied"
      role="status"
    >
      <div aria-hidden="true" className="portal-access-denied-mark">
        !
      </div>

      <div className="portal-access-denied-copy">
        <p className="portal-page-eyebrow">Authorization</p>

        <h2 className="portal-page-title" id="portal-access-denied-title">
          {title}
        </h2>

        <p className="portal-page-description">{description}</p>

        {guidance ? <div className="portal-access-denied-guidance">{guidance}</div> : null}
      </div>
    </section>
  );
}
