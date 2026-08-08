export type DashboardMediaLibraryStatus = "available" | "unavailable";

export type DashboardMediaLibrary = Readonly<{
  id: string;
  label: string;
  count?: number;
  status: DashboardMediaLibraryStatus;
  detail?: string;
}>;

export type DashboardMediaSnapshot = Readonly<{
  generatedAt: string;
  libraries: readonly DashboardMediaLibrary[];
}>;

function normalizeRequiredText(value: string, fieldName: string): string {
  const normalized = value.trim();

  if (!normalized) {
    throw new Error(`${fieldName} must not be empty.`);
  }

  return normalized;
}

function normalizeOptionalText(value: string | undefined): string | undefined {
  const normalized = value?.trim();

  return normalized ? normalized : undefined;
}

function normalizeTimestamp(value: string): string {
  const timestamp = new Date(value);

  if (Number.isNaN(timestamp.getTime())) {
    throw new Error("generatedAt must be a valid timestamp.");
  }

  return timestamp.toISOString();
}

function normalizeCount(
  count: number | undefined,
  status: DashboardMediaLibraryStatus
): number | undefined {
  if (status === "unavailable") {
    if (count !== undefined) {
      throw new Error("Unavailable media libraries cannot have a count.");
    }

    return undefined;
  }

  if (count === undefined || !Number.isInteger(count) || count < 0) {
    throw new Error("Available media libraries require a nonnegative integer count.");
  }

  return count;
}

export function createDashboardMediaLibrary(library: DashboardMediaLibrary): DashboardMediaLibrary {
  const id = normalizeRequiredText(library.id, "library.id").toLowerCase();

  const label = normalizeRequiredText(library.label, "library.label");

  const count = normalizeCount(library.count, library.status);

  const detail = normalizeOptionalText(library.detail);

  return {
    id,
    label,
    status: library.status,
    ...(count === undefined
      ? {}
      : {
          count
        }),
    ...(detail === undefined
      ? {}
      : {
          detail
        })
  };
}

export function createDashboardMediaSnapshot(
  snapshot: DashboardMediaSnapshot
): DashboardMediaSnapshot {
  const libraries = snapshot.libraries.map(createDashboardMediaLibrary);

  const libraryIds = new Set(libraries.map((library) => library.id));

  if (libraryIds.size !== libraries.length) {
    throw new Error("Dashboard media library IDs must be unique.");
  }

  return {
    generatedAt: normalizeTimestamp(snapshot.generatedAt),
    libraries
  };
}
