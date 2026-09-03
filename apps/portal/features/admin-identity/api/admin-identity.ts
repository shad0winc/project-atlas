import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export type AdminUser = Readonly<{
  userId: string;
  username: string;
  displayName: string;
  firstName: string | null;
  lastName: string | null;
  email: string | null;
  discordAccount: string | null;
  emailNotificationsEnabled: boolean;
  discordNotificationsEnabled: boolean;
  roles: readonly string[];
  status: string;
  jellyfinUserId: string | null;
}>;

export type AdminUserCreateInput = Readonly<{
  username: string;
  displayName: string;
  email: string;
  password: string;
  roles: readonly string[];
  firstName?: string;
  lastName?: string;
  discordAccount?: string;
  emailNotificationsEnabled?: boolean;
  discordNotificationsEnabled?: boolean;
}>;

export type AdminUserUpdateInput = Readonly<{
  displayName?: string;
  firstName?: string | null;
  lastName?: string | null;
  email?: string;
  discordAccount?: string | null;
  emailNotificationsEnabled?: boolean;
  discordNotificationsEnabled?: boolean;
  status?: string;
  roles?: readonly string[];
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
  role: string;
  days: number;
}>;

type AdminUserTransport = Readonly<{
  user_id: string;
  username: string;
  display_name: string;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
  discord_account?: string | null;
  email_notifications_enabled?: boolean;
  discord_notifications_enabled?: boolean;
  roles: readonly string[];
  status: string;
  jellyfin_user_id?: string | null;
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
    firstName: optionalString(response.first_name),
    lastName: optionalString(response.last_name),
    email: optionalString(response.email),
    discordAccount: optionalString(response.discord_account),
    emailNotificationsEnabled: response.email_notifications_enabled === true,
    discordNotificationsEnabled: response.discord_notifications_enabled === true,
    roles: response.roles.map((role) => requiredString(role, "role")),
    status: requiredString(response.status, "status"),
    jellyfinUserId: optionalString(response.jellyfin_user_id)
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

export async function createAdminUser(
  input: AdminUserCreateInput
): Promise<AdminUser> {
  const response = await authenticatedAtlasApiRequest<AdminUserTransport>(
    "/admin/users",
    {
      method: "POST",
      ...mutationOptions({
        username: requiredString(input.username, "username"),
        display_name: requiredString(input.displayName, "display name"),
        email: requiredString(input.email, "email"),
        password: requiredString(input.password, "password"),
        roles: [...input.roles],
        ...(input.firstName?.trim()
          ? { first_name: input.firstName.trim() }
          : {}),
        ...(input.lastName?.trim()
          ? { last_name: input.lastName.trim() }
          : {}),
        ...(input.discordAccount?.trim()
          ? { discord_account: input.discordAccount.trim() }
          : {}),
        email_notifications_enabled:
          input.emailNotificationsEnabled === true,
        discord_notifications_enabled:
          input.discordNotificationsEnabled === true
      })
    }
  );

  return mapUser(response);
}


export async function updateAdminUser(
  identifier: string,
  updates: AdminUserUpdateInput
): Promise<AdminUser> {
  const normalized = requiredString(identifier, "user identifier");

  const body: Record<string, unknown> = {};

  if (updates.displayName !== undefined) {
    body.display_name = requiredString(
      updates.displayName,
      "display name"
    );
  }

  if (updates.firstName !== undefined) {
    body.first_name = updates.firstName?.trim() || null;
  }

  if (updates.lastName !== undefined) {
    body.last_name = updates.lastName?.trim() || null;
  }

  if (updates.email !== undefined) {
    body.email = requiredString(updates.email, "email");
  }

  if (updates.discordAccount !== undefined) {
    body.discord_account =
      updates.discordAccount?.trim() || null;
  }

  if (updates.emailNotificationsEnabled !== undefined) {
    body.email_notifications_enabled =
      updates.emailNotificationsEnabled;
  }

  if (updates.discordNotificationsEnabled !== undefined) {
    body.discord_notifications_enabled =
      updates.discordNotificationsEnabled;
  }

  if (updates.status !== undefined) {
    body.status = updates.status;
  }

  if (updates.roles !== undefined) {
    body.roles = [...updates.roles];
  }

  const response = await authenticatedAtlasApiRequest<AdminUserTransport>(
    `/admin/users/${encodeURIComponent(normalized)}`,
    {
      method: "PATCH",
      ...mutationOptions(body)
    }
  );

  return mapUser(response);
}

export async function setAdminUserPassword(
  identifier: string,
  newPassword: string
): Promise<void> {
  const normalized = requiredString(identifier, "user identifier");
  const password = requiredString(newPassword, "new password");

  await authenticatedAtlasApiRequest<{ status: string }>(
    `/admin/users/${encodeURIComponent(normalized)}/password`,
    {
      method: "POST",
      ...mutationOptions({
        new_password: password
      })
    }
  );
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
