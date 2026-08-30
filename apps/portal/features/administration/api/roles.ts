import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type AdminRole = Readonly<{
  name: string;
  displayName: string;
  description: string;
  permissions: readonly string[];
  protected: boolean;
  assignable: boolean;
  source: string;
}>;

export type AdminRoleCatalog = Readonly<{
  roles: readonly AdminRole[];
  permissions: readonly string[];
}>;

export type AssignableRole = Readonly<{
  name: string;
  displayName: string;
  assignable: boolean;
}>;

type AssignableRoleTransport = Readonly<{
  name: string;
  display_name: string;
  assignable: boolean;
}>;

type AssignableRoleCatalogTransport = Readonly<{
  roles: readonly AssignableRoleTransport[];
}>;

type AdminRoleTransport = Readonly<{
  name: string;
  display_name: string;
  description: string;
  permissions: readonly string[];
  protected: boolean;
  assignable: boolean;
  source: string;
}>;

type AdminRoleCatalogTransport = Readonly<{
  roles: readonly AdminRoleTransport[];
  permissions: readonly string[];
}>;

export type AdminRoleCreateInput = Readonly<{
  name: string;
  displayName: string;
  description: string;
  permissions: readonly string[];
  assignable: boolean;
}>;

export type AdminRoleUpdateInput = Readonly<{
  displayName?: string;
  description?: string;
  permissions?: readonly string[];
  assignable?: boolean;
}>;

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} is missing from the Atlas API response.`);
  }
  return value.trim();
}

function mapRole(role: AdminRoleTransport): AdminRole {
  return {
    name: requiredString(role.name, "role name"),
    displayName: requiredString(role.display_name, "role display_name"),
    description: typeof role.description === "string" ? role.description : "",
    permissions: role.permissions.map((permission) => requiredString(permission, "permission")),
    protected: Boolean(role.protected),
    assignable: Boolean(role.assignable),
    source: requiredString(role.source, "role source")
  };
}

function mutationOptions(body: Readonly<Record<string, unknown>>) {
  return {
    cache: "no-store" as const,
    body,
    retryPolicy: { maxRetries: 0, baseDelayMs: 250, maxDelayMs: 5_000 }
  };
}

export async function loadAdminRoleCatalog(signal?: AbortSignal): Promise<AdminRoleCatalog> {
  const response = await authenticatedAtlasApiRequest<AdminRoleCatalogTransport>("/admin/roles", {
    method: "GET",
    cache: "no-store",
    signal
  });
  return {
    roles: response.roles.map(mapRole),
    permissions: response.permissions.map((permission) => requiredString(permission, "permission"))
  };
}


export async function loadAssignableRoleCatalog(signal?: AbortSignal): Promise<readonly AssignableRole[]> {
  const response = await authenticatedAtlasApiRequest<AssignableRoleCatalogTransport>("/admin/roles/assignable", {
    method: "GET",
    cache: "no-store",
    signal
  });
  return response.roles.map((role) => ({
    name: requiredString(role.name, "role name"),
    displayName: requiredString(role.display_name, "role display_name"),
    assignable: Boolean(role.assignable)
  }));
}

export async function createAdminRole(input: AdminRoleCreateInput): Promise<void> {
  await authenticatedAtlasApiRequest<unknown>("/admin/roles", {
    method: "POST",
    ...mutationOptions({
      name: input.name.trim(),
      display_name: input.displayName.trim(),
      description: input.description.trim(),
      permissions: input.permissions,
      assignable: input.assignable
    })
  });
}

export async function updateAdminRole(name: string, input: AdminRoleUpdateInput): Promise<void> {
  await authenticatedAtlasApiRequest<unknown>(`/admin/roles/${encodeURIComponent(name)}`, {
    method: "PATCH",
    ...mutationOptions({
      ...(input.displayName !== undefined ? { display_name: input.displayName.trim() } : {}),
      ...(input.description !== undefined ? { description: input.description.trim() } : {}),
      ...(input.permissions !== undefined ? { permissions: input.permissions } : {}),
      ...(input.assignable !== undefined ? { assignable: input.assignable } : {})
    })
  });
}

export async function deleteAdminRole(name: string): Promise<void> {
  await authenticatedAtlasApiRequest<unknown>(`/admin/roles/${encodeURIComponent(name)}`, {
    method: "DELETE",
    ...mutationOptions({})
  });
}
