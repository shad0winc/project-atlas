import { Badge } from "../../../components/ui/Badge";
import { Card } from "../../../components/ui/Card";

import type { PortalOperationsComparison } from "../types/operations";

type OperationsComparisonCardProps = Readonly<{
  comparison: PortalOperationsComparison;
}>;

function formatSignedValue(value: number | null): string {
  if (value === null) {
    return "Not available";
  }

  if (value > 0) {
    return `+${value}`;
  }

  return value.toString();
}

function formatCount(value: number | null): string {
  return value === null ? "Not available" : value.toLocaleString("en-US");
}

export function OperationsComparisonCard({
  comparison
}: OperationsComparisonCardProps): React.ReactElement {
  if (comparison.status === "unavailable") {
    return (
      <Card>
        <h3>Operations comparison</h3>

        <Badge>Unavailable</Badge>

        <p>{comparison.detail ?? "A previous Operations report is required for comparison."}</p>
      </Card>
    );
  }

  return (
    <Card>
      <h3>Operations comparison</h3>

      <Badge variant="success">Available</Badge>

      <p>Score change: {formatSignedValue(comparison.scoreDelta)}</p>

      <p>Attention change: {formatSignedValue(comparison.attentionDelta)}</p>

      <p>Added: {formatCount(comparison.addedCount)}</p>

      <p>Removed: {formatCount(comparison.removedCount)}</p>

      <p>Changed: {formatCount(comparison.changedCount)}</p>

      <p>Unchanged: {formatCount(comparison.unchangedCount)}</p>

      <p>Total differences: {formatCount(comparison.differenceCount)}</p>
    </Card>
  );
}
