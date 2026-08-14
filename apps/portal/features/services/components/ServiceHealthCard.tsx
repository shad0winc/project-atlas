import { Card } from "../../../components/ui/Card";

import type { ServiceLifecycleHealth } from "../types/services";

type ServiceHealthCardProps = Readonly<{
  health: ServiceLifecycleHealth;
}>;

function scoreLabel(score: number | null): string {
  return score === null ? "Not reported" : `${score}%`;
}

export function ServiceHealthCard({ health }: ServiceHealthCardProps): React.ReactElement {
  return (
    <Card>
      <p>Service health</p>
      <h3>{health.status}</h3>
      <p>Health score: {scoreLabel(health.score)}</p>
      <p>Total services: {health.totalServices}</p>
      <p>
        Healthy {health.healthy} · Degraded {health.degraded} · Unhealthy {health.unhealthy} ·
        Unknown {health.unknown}
      </p>
      {health.evaluatedAt ? (
        <time dateTime={health.evaluatedAt}>
          Evaluated {new Date(health.evaluatedAt).toLocaleString()}
        </time>
      ) : null}
    </Card>
  );
}
