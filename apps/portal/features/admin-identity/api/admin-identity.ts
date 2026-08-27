import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type AdminUser = Readonly<{
  userId: string;
  username: string;
  displayName: string;
  roles: readonly string[];
  status: string;
}>;

export type AdminInvitation = Readonly<{
  inviteId: string;
  email: string | null;
  role: string;
  status: string;
  createdAt: string | null;
  expiresAt: string | null;
  token?: string;
}>;

export type InvitationCreateInput = Readonly<{
  email?: string;
  role: "admin" | "user";
  days: number;
}>;

type AdminUserTransport = Readonly<{
  user_id: string;
  username: string;
  display_name: string;
  roles: readonly string[];
  status: string;
}>;

type AdminUserListTransport = Readonly<{
  users: readonly AdminUserTransport[];
}>;

type AdminInvitationTransport = Readonly<Record<string, unknown>> & {
  readonly invite_id?: string;
  readonly invitation_id?: string;
  readonly email?: string | null;
  readonly role?: string;
  readonly status?: string;
  readonly created_at?: string | null;
  readonly expires_at?: string | null;
  readonly expires?: string | null;
  readonly token?: string;
};

type AdminInvitationListTransport = Readonly<{
  items: readonly AdminInvitationTransport[];
}>;

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${label} is missing from the Atlas API response.`);
  }
  return value.trim();
}

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function mapUser(response: AdminUserTransport): AdminUser {
  return {
    userId: requiredString(response.user_id, "user_id"),
    username: requiredString(response.username, "username"),
    displayName: requiredString(response.display_name, "display_name"),
    roles: response.roles.map((role) => requiredString(role, "role")),
    status: requiredString(response.status, "status")
  };
}

function mapInvitation(response: AdminInvitationTransport): AdminInvitation {
  const inviteId = response.invite_id ?? response.invitation_id;

  return {
    inviteId: requiredString(inviteId, "invite_id"),
    email: optionalString(response.email),
    role: requiredString(response.role, "role"),
    status: requiredString(response.status, "status"),
    createdAt: optionalString(response.created_at),
    expiresAt: optionalString(response.expires_at ?? response.expires),
    ...(typeof response.token === "string" && response.token.trim()
      ? { token: response.token.trim() }
      : {})
  };
}

function mutationOptions(body: Readonly<Record<string, unknown>>) {
  return {
    cache: "no-store" as const,
    body,
    retryPolicy: {
      maxRetries: 0,
      baseDelayMs: 250,
      maxDelayMs: 5_000
    }
  };
}

export async function loadAdminUsers(signal?: AbortSignal): Promise<readonly AdminUser[]> {
  const response = await authenticatedAtlasApiRequest<AdminUserListTransport>("/admin/users", {
    method: "GET",
    cache: "no-store",
    signal
  });

  return response.users.map(mapUser);
}

export async function loadAdminUser(
  identifier: string,
  signal?: AbortSignal
): Promise<AdminUser> {
  const normalized = requiredString(identifier, "user identifier");
  const response = await authenticatedAtlasApiRequest<AdminUserTransport>(
    `/admin/users/${encodeURIComponent(normalized)}`,
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return mapUser(response);
}

export async function updateAdminUser(
  identifier: string,
  updates: Readonly<{ status?: string; roles?: readonly string[] }>
): Promise<AdminUser> {
  const normalized = requiredString(identifier, "user identifier");

  const response = await authenticatedAtlasApiRequest<AdminUserTransport>(
    `/admin/users/${encodeURIComponent(normalized)}`,
    {
      method: "PATCH",
      ...mutationOptions(updates)
    }
  );

  return mapUser(response);
}

export async function loadAdminInvitations(
  signal?: AbortSignal
): Promise<readonly AdminInvitation[]> {
  const response =
    await authenticatedAtlasApiRequest<AdminInvitationListTransport>("/admin/invitations", {
      method: "GET",
      cache: "no-store",
      signal
    });

  return response.items.map(mapInvitation);
}

export async function loadAdminInvitation(
  inviteId: string,
  signal?: AbortSignal
): Promise<AdminInvitation> {
  const normalized = requiredString(inviteId, "invite_id");
  const response = await authenticatedAtlasApiRequest<AdminInvitationTransport>(
    `/admin/invitations/${encodeURIComponent(normalized)}`,
    {
      method: "GET",
      cache: "no-store",
      signal
    }
  );

  return mapInvitation(response);
}

export async function createAdminInvitation(
  input: InvitationCreateInput
): Promise<AdminInvitation> {
  if (!Number.isInteger(input.days) || input.days < 1) {
    throw new Error("Invitation expiration must be at least one day.");
  }

  const response = await authenticatedAtlasApiRequest<AdminInvitationTransport>(
    "/admin/invitations",
    {
      method: "POST",
      ...mutationOptions({
        ...(input.email?.trim() ? { email: input.email.trim() } : {}),
        role: input.role,
        days: input.days
      })
    }
  );

  return mapInvitation(response);
}

export async function revokeAdminInvitation(inviteId: string): Promise<AdminInvitation> {
  const normalized = requiredString(inviteId, "invite_id");

  const response = await authenticatedAtlasApiRequest<AdminInvitationTransport>(
    `/admin/invitations/${encodeURIComponent(normalized)}/revoke`,
    {
      method: "POST",
      ...mutationOptions({})
    }
  );

  return mapInvitation(response);
}
