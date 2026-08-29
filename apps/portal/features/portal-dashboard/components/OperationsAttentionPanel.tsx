import { Badge } from "../../../components/ui/Badge";
import { Card } from "../../../components/ui/Card";

import type { PortalOperationsAttention, PortalOperationsSnapshot } from "../types/operations";

type OperationsAttentionPanelProps = Readonly<{
  operations: PortalOperationsSnapshot;
}>;

function severityVariant(severity: PortalOperationsAttention["severity"]): "default" | "primary" {
  return severity === "warning" ? "primary" : "default";
}

export function OperationsAttentionPanel({
  operations
}: OperationsAttentionPanelProps): React.ReactElement {
  if (operations.status === "unavailable") {
    return (
      <Card>
        <h3>Recent attention</h3>

        <Badge>Unavailable</Badge>

        <p>{operations.detail ?? "Operations attention findings are currently unavailable."}</p>
      </Card>
    );
  }

  if (!operations.recentAttention.length) {
    return (
      <Card>
        <h3>Recent attention</h3>

        <Badge variant="success">Clear</Badge>

        <p>No findings required attention in this Operations snapshot.</p>
      </Card>
    );
  }

  return (
    <Card>
      <h3>Recent attention</h3>

      <Badge variant="primary">
        {operations.recentAttention.length} finding
        {operations.recentAttention.length === 1 ? "" : "s"}
      </Badge>

      <ul className="status-list">
        {operations.recentAttention.map((finding) => (
          <li className="status-list__item" key={`${finding.section}:${finding.identifier}`}>
            <div>
              <strong>{finding.name}</strong>

              <p>{finding.message}</p>

              {finding.recommendation ? <p>Recommendation: {finding.recommendation}</p> : null}
            </div>

            <span className="status-list__state">
              <Badge variant={severityVariant(finding.severity)}>{finding.severity}</Badge>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}
