import { Card } from "../../../components/ui/Card";

type PortalHealthCardProps = Readonly<{
  health: Readonly<{
    status: string;
    service: string;
    apiVersion: string;
  }>;
  generatedAt: string;
}>;

export function PortalHealthCard({
  health,
  generatedAt
}: PortalHealthCardProps): React.ReactElement {
  return (
    <Card>
      <h3>System Health</h3>

      <p>{health.service}</p>

      <p>
        Status: {health.status}
      </p>

      <p>
        Version: {health.apiVersion}
      </p>

      <time dateTime={generatedAt}>
        Updated {new Date(generatedAt).toLocaleString()}
      </time>
    </Card>
  );
}
