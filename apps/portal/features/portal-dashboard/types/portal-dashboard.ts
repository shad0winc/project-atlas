export type PortalDashboardSnapshot = Readonly<{
  generatedAt: string;
  health: Readonly<{
    status: string;
    service: string;
    apiVersion: string;
  }>;
  operational: unknown;
  media: unknown;
  operations: unknown;
  scheduler: unknown;
}>;


export function createPortalDashboardSnapshot(
  value: PortalDashboardSnapshot
): PortalDashboardSnapshot {

  const timestamp = new Date(
    value.generatedAt
  );

  if (Number.isNaN(timestamp.getTime())) {
    throw new Error(
      "generatedAt must be a valid timestamp."
    );
  }

  return {
    ...value,
    generatedAt: timestamp.toISOString()
  };
}
