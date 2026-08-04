import { Badge } from "../../../components/ui/Badge";
import { Card } from "../../../components/ui/Card";

import type {
  PortalOperationsSnapshot
} from "../types/operations";


type OperationsSummaryCardProps = Readonly<{
  operations: PortalOperationsSnapshot;
}>;


function statusVariant(
  status: "healthy" | "warning" | "critical" | "unknown"
): "default" | "success" | "primary" {
  if (status === "healthy") {
    return "success";
  }

  if (status === "warning") {
    return "primary";
  }

  return "default";
}


export function OperationsSummaryCard({
  operations
}: OperationsSummaryCardProps): React.ReactElement {
  if (
    operations.status === "unavailable" ||
    operations.summary === null
  ) {
    return (
      <Card>
        <h3>Operations</h3>

        <Badge>
          Unavailable
        </Badge>

        <p>
          {operations.detail ??
            "No Operations report is available."}
        </p>
      </Card>
    );
  }

  const summary = operations.summary;

  return (
    <Card>
      <h3>Operations</h3>

      <Badge variant={statusVariant(summary.status)}>
        {summary.status}
      </Badge>

      <p>
        Score: {summary.score}
      </p>

      <p>
        Attention: {summary.attentionCount}
      </p>

      <time dateTime={summary.generatedAt}>
        Generated{" "}
        {new Date(
          summary.generatedAt
        ).toLocaleString()}
      </time>
    </Card>
  );
}
