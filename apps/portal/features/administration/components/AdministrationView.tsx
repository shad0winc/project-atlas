import Link from "next/link";

import { Card } from "../../../components/ui/Card";
import { usePermission } from "../../../lib/authorization";
import { PORTAL_ROUTES } from "../../../lib/navigation/portal";

const administrationDestinations = [
  {
    route: PORTAL_ROUTES.users,
    title: "Users and access",
    description:
      "Manage Atlas users, roles, status, and invitations through the supported identity workflow."
  },
  {
    route: PORTAL_ROUTES.services,
    title: "Managed services",
    description: "Review Atlas-managed service health, runtime details, and maintenance history."
  },
  {
    route: PORTAL_ROUTES.requests,
    title: "Requests",
    description:
      "Review media request lifecycle and the request workflows available to your account."
  },
  {
    route: PORTAL_ROUTES.media,
    title: "Media",
    description: "Open the supported media discovery and request experience."
  },
  {
    route: PORTAL_ROUTES.sports,
    title: "Sports",
    description: "Open the supported sports scheduling and request experience."
  }
] as const;

export function AdministrationView(): React.ReactElement {
  const { can } = usePermission();
  const visibleDestinations = administrationDestinations.filter(({ route }) =>
    can(route.permission)
  );

  return (
    <section aria-labelledby="administration-surfaces-title" className="administration-surface">
      <div className="administration-surface-heading">
        <h3 id="administration-surfaces-title">Management surfaces</h3>
        <p>
          Administration stays inside Atlas-supported workflows. Backend applications and
          infrastructure administration remain outside this Portal surface.
        </p>
      </div>

      <div className="administration-grid">
        {visibleDestinations.map(({ route, title, description }) => (
          <Card className="administration-card" key={route.id}>
            <div className="administration-card-content">
              <p className="portal-page-eyebrow">{route.label}</p>
              <h4>{title}</h4>
              <p>{description}</p>
            </div>

            <Link className="button button--secondary" href={route.path}>
              Open {route.label}
            </Link>
          </Card>
        ))}
      </div>
    </section>
  );
}
