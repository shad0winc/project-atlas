export type MediaLibraryStatus = "available" | "unavailable";

export type MediaLibrary = Readonly<{
  id: string;
  label: string;
  status: MediaLibraryStatus;
  count?: number;
  detail?: string;
}>;

export type MediaSnapshot = Readonly<{
  generatedAt: string;
  libraries: readonly MediaLibrary[];
}>;

export type MediaSummary = Readonly<{
  libraryCount: number;
  availableLibraryCount: number;
  unavailableLibraryCount: number;
  totalItemCount: number;
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

function normalizeCount(count: number | undefined, status: MediaLibraryStatus): number | undefined {
  if (status === "unavailable") {
    if (count !== undefined) {
      throw new Error("Unavailable media libraries cannot have an item count.");
    }

    return undefined;
  }

  if (count === undefined || !Number.isInteger(count) || count < 0) {
    throw new Error("Available media libraries require a nonnegative integer item count.");
  }

  return count;
}

export function createMediaLibrary(library: MediaLibrary): MediaLibrary {
  const id = normalizeRequiredText(library.id, "library.id").toLowerCase();
  const label = normalizeRequiredText(library.label, "library.label");
  const count = normalizeCount(library.count, library.status);
  const detail = normalizeOptionalText(library.detail);

  return {
    id,
    label,
    status: library.status,
    ...(count === undefined ? {} : { count }),
    ...(detail === undefined ? {} : { detail })
  };
}

export function createMediaSnapshot(snapshot: MediaSnapshot): MediaSnapshot {
  const libraries = snapshot.libraries.map(createMediaLibrary);
  const libraryIds = new Set(libraries.map((library) => library.id));

  if (libraryIds.size !== libraries.length) {
    throw new Error("Media library IDs must be unique.");
  }

  return {
    generatedAt: normalizeTimestamp(snapshot.generatedAt),
    libraries
  };
}

export function summarizeMediaSnapshot(snapshot: MediaSnapshot): MediaSummary {
  const availableLibraries = snapshot.libraries.filter((library) => library.status === "available");

  return {
    libraryCount: snapshot.libraries.length,
    availableLibraryCount: availableLibraries.length,
    unavailableLibraryCount: snapshot.libraries.length - availableLibraries.length,
    totalItemCount: availableLibraries.reduce((total, library) => total + (library.count ?? 0), 0)
  };
}
