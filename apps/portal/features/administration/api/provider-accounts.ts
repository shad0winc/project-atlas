import { authenticatedAtlasApiRequest } from "../../../lib/services/authenticated";

export interface AdminSportsAccount {
  readonly sourceId: string;
  readonly displayName: string;
  readonly accountDisplayName: string;
  readonly enabled: boolean;
  readonly kind: string;
  readonly trustClass: string;
  readonly priority: number;
  readonly maxConnections: number;
  readonly expiresAt: string | null;
  readonly backendConfigured: boolean;
}

export interface AdminSportsProvider {
  readonly providerId: string;
  readonly displayName: string;
  readonly accountCount: number;
  readonly enabledAccountCount: number;
  readonly configuredMaxConnections: number;
  readonly enabledMaxConnections: number;
  readonly accounts: readonly AdminSportsAccount[];
}

export interface AdminSportsResourceAccount {
  readonly sourceId: string;
  readonly enabled: boolean;
  readonly capacity: number;
  readonly active: number;
  readonly available: number;
}

export interface AdminSportsResourcePool {
  readonly totalCapacity: number;
  readonly active: number;
  readonly available: number;
  readonly accounts: readonly AdminSportsResourceAccount[];
}

export interface AdminSportsConnection {
  readonly accountId: number;
  readonly name: string;
  readonly accountType: string;
  readonly enabled: boolean;
  readonly configuredMaxConnections: number;
  readonly credentialsConfigured: boolean;
}

export interface AdminSportsConnectionTest {
  readonly ok: boolean;
  readonly status: string;
  readonly expiresAt: string | null;
  readonly providerMaxConnections: number | null;
  readonly activeConnections: number | null;
}

export interface CreateAdminSportsProviderAccountInput {
  readonly sourceId: string;
  readonly providerDisplayName: string;
  readonly accountDisplayName: string;
  readonly serverUrl: string;
  readonly username: string;
  readonly password: string;
  readonly maxConnections: number;
  readonly priority: number;
}

export interface UpdateAdminSportsAccountInput {
  readonly accountDisplayName?: string;
  readonly enabled?: boolean;
  readonly maxConnections?: number;
}

export interface UpdateAdminSportsCredentialsInput {
  readonly serverUrl?: string;
  readonly username?: string;
  readonly password?: string;
}

interface AccountTransport {
  readonly source_id: unknown;
  readonly display_name: unknown;
  readonly account_display_name: unknown;
  readonly enabled: unknown;
  readonly kind: unknown;
  readonly trust_class: unknown;
  readonly priority: unknown;
  readonly max_connections: unknown;
  readonly expires_at: unknown;
  readonly backend_configured: unknown;
}

interface ProviderTransport {
  readonly provider_id: unknown;
  readonly display_name: unknown;
  readonly account_count: unknown;
  readonly enabled_account_count: unknown;
  readonly configured_max_connections: unknown;
  readonly enabled_max_connections: unknown;
  readonly accounts: unknown;
}

interface ProviderListTransport {
  readonly providers: unknown;
}

interface ResourceAccountTransport {
  readonly source_id: unknown;
  readonly enabled: unknown;
  readonly capacity: unknown;
  readonly active: unknown;
  readonly available: unknown;
}

interface ResourcePoolTransport {
  readonly total_capacity: unknown;
  readonly active: unknown;
  readonly available: unknown;
  readonly accounts: unknown;
}

interface ConnectionTransport {
  readonly account_id: unknown;
  readonly name: unknown;
  readonly account_type: unknown;
  readonly enabled: unknown;
  readonly configured_max_connections: unknown;
  readonly credentials_configured: unknown;
}

interface ConnectionTestTransport {
  readonly ok: unknown;
  readonly status: unknown;
  readonly expires_at: unknown;
  readonly provider_max_connections: unknown;
  readonly active_connections: unknown;
}

interface RemoveTransport {
  readonly removed: unknown;
  readonly source_id: unknown;
}

const privateKeys = new Set([
  "backend_reference",
  "password",
  "username",
  "server_url",
  "stream_url",
  "token",
  "authorization",
  "access_token",
  "refresh_token",
  "api_key",
  "apikey",
  "secret"
]);

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${label} must be an object.`);
  }

  return value as Record<string, unknown>;
}

function assertPublicSafe(value: unknown, path = "response"): void {
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertPublicSafe(item, `${path}[${index}]`));
    return;
  }

  if (typeof value !== "object" || value === null) return;

  for (const [key, child] of Object.entries(value)) {
    if (privateKeys.has(key.trim().toLowerCase())) {
      throw new Error(`Private provider field crossed the Portal boundary at ${path}.${key}.`);
    }

    assertPublicSafe(child, `${path}.${key}`);
  }
}

function requiredString(value: unknown, label: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`${label} must be a non-empty string.`);
  }

  return value.trim();
}

function booleanValue(value: unknown, label: string): boolean {
  if (typeof value !== "boolean") {
    throw new Error(`${label} must be a boolean.`);
  }

  return value;
}

function integer(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value)) {
    throw new Error(`${label} must be an integer.`);
  }

  return value;
}

function nonNegativeInteger(value: unknown, label: string): number {
  const parsed = integer(value, label);

  if (parsed < 0) {
    throw new Error(`${label} must be non-negative.`);
  }

  return parsed;
}

function positiveInteger(value: unknown, label: string): number {
  const parsed = integer(value, label);

  if (parsed <= 0) {
    throw new Error(`${label} must be positive.`);
  }

  return parsed;
}

function nullableString(value: unknown, label: string): string | null {
  if (value === null) return null;

  return requiredString(value, label);
}

function nullableNonNegativeInteger(value: unknown, label: string): number | null {
  if (value === null) return null;

  return nonNegativeInteger(value, label);
}

function encodedId(value: string, label: string): string {
  return encodeURIComponent(requiredString(value, label));
}

function mapAccount(value: unknown): AdminSportsAccount {
  const item = record(value, "provider account") as unknown as AccountTransport;

  return {
    sourceId: requiredString(item.source_id, "provider account source id"),
    displayName: requiredString(item.display_name, "provider account display name"),
    accountDisplayName: requiredString(item.account_display_name, "provider account label"),
    enabled: booleanValue(item.enabled, "provider account enabled"),
    kind: requiredString(item.kind, "provider account kind"),
    trustClass: requiredString(item.trust_class, "provider account trust class"),
    priority: nonNegativeInteger(item.priority, "provider account priority"),
    maxConnections: positiveInteger(item.max_connections, "provider account max connections"),
    expiresAt: nullableString(item.expires_at, "provider account expiry"),
    backendConfigured: booleanValue(item.backend_configured, "provider account backend configured")
  };
}

function mapProvider(value: unknown): AdminSportsProvider {
  const item = record(value, "provider") as unknown as ProviderTransport;

  if (!Array.isArray(item.accounts)) {
    throw new Error("provider accounts must be an array.");
  }

  return {
    providerId: requiredString(item.provider_id, "provider id"),
    displayName: requiredString(item.display_name, "provider display name"),
    accountCount: nonNegativeInteger(item.account_count, "provider account count"),
    enabledAccountCount: nonNegativeInteger(
      item.enabled_account_count,
      "provider enabled account count"
    ),
    configuredMaxConnections: nonNegativeInteger(
      item.configured_max_connections,
      "provider configured capacity"
    ),
    enabledMaxConnections: nonNegativeInteger(
      item.enabled_max_connections,
      "provider enabled capacity"
    ),
    accounts: item.accounts.map(mapAccount)
  };
}

function mapProviderList(value: unknown): readonly AdminSportsProvider[] {
  assertPublicSafe(value);

  const response = record(value, "provider list") as unknown as ProviderListTransport;

  if (!Array.isArray(response.providers)) {
    throw new Error("providers must be an array.");
  }

  return response.providers.map(mapProvider);
}

function mapResourcePool(value: unknown): AdminSportsResourcePool {
  assertPublicSafe(value);

  const response = record(value, "resource pool") as unknown as ResourcePoolTransport;

  if (!Array.isArray(response.accounts)) {
    throw new Error("resource-pool accounts must be an array.");
  }

  return {
    totalCapacity: nonNegativeInteger(response.total_capacity, "total capacity"),
    active: nonNegativeInteger(response.active, "active connections"),
    available: nonNegativeInteger(response.available, "available connections"),
    accounts: response.accounts.map((value) => {
      const item = record(value, "resource-pool account") as unknown as ResourceAccountTransport;

      return {
        sourceId: requiredString(item.source_id, "resource-pool source id"),
        enabled: booleanValue(item.enabled, "resource-pool account enabled"),
        capacity: nonNegativeInteger(item.capacity, "resource-pool capacity"),
        active: nonNegativeInteger(item.active, "resource-pool active"),
        available: nonNegativeInteger(item.available, "resource-pool available")
      };
    })
  };
}

function mapConnection(value: unknown): AdminSportsConnection {
  assertPublicSafe(value);

  const item = record(value, "provider connection") as unknown as ConnectionTransport;

  return {
    accountId: positiveInteger(item.account_id, "provider connection account id"),
    name: requiredString(item.name, "provider connection name"),
    accountType: requiredString(item.account_type, "provider connection account type"),
    enabled: booleanValue(item.enabled, "provider connection enabled"),
    configuredMaxConnections: positiveInteger(
      item.configured_max_connections,
      "provider connection configured capacity"
    ),
    credentialsConfigured: booleanValue(
      item.credentials_configured,
      "provider credentials configured"
    )
  };
}

function mapConnectionTest(value: unknown): AdminSportsConnectionTest {
  assertPublicSafe(value);

  const item = record(value, "provider connection test") as unknown as ConnectionTestTransport;

  return {
    ok: booleanValue(item.ok, "provider connection test ok"),
    status: requiredString(item.status, "provider connection test status"),
    expiresAt: nullableString(item.expires_at, "provider connection expiry"),
    providerMaxConnections: nullableNonNegativeInteger(
      item.provider_max_connections,
      "provider connection upstream capacity"
    ),
    activeConnections: nullableNonNegativeInteger(
      item.active_connections,
      "provider connection active connections"
    )
  };
}

export async function loadAdminSportsProviders(): Promise<readonly AdminSportsProvider[]> {
  const response = await authenticatedAtlasApiRequest<unknown>("/admin/sports/providers", {
    method: "GET",
    cache: "no-store"
  });

  return mapProviderList(response);
}

export async function loadAdminSportsResourcePool(): Promise<AdminSportsResourcePool> {
  const response = await authenticatedAtlasApiRequest<unknown>(
    "/admin/sports/providers/resource-pool",
    {
      method: "GET",
      cache: "no-store"
    }
  );

  return mapResourcePool(response);
}

export async function updateAdminSportsProvider(
  providerId: string,
  displayName: string
): Promise<readonly AdminSportsProvider[]> {
  const response = await authenticatedAtlasApiRequest<unknown>(
    `/admin/sports/providers/${encodedId(providerId, "provider id")}`,
    {
      method: "PATCH",
      cache: "no-store",
      body: {
        display_name: requiredString(displayName, "provider display name")
      }
    }
  );

  return mapProviderList(response);
}

export async function updateAdminSportsAccount(
  providerId: string,
  sourceId: string,
  input: UpdateAdminSportsAccountInput
): Promise<readonly AdminSportsProvider[]> {
  const body: Record<string, unknown> = {};

  if (input.accountDisplayName !== undefined) {
    body.account_display_name = requiredString(input.accountDisplayName, "account display name");
  }

  if (input.enabled !== undefined) {
    body.enabled = input.enabled;
  }

  if (input.maxConnections !== undefined) {
    body.max_connections = positiveInteger(input.maxConnections, "account max connections");
  }

  if (Object.keys(body).length === 0) {
    throw new Error("At least one provider-account field is required.");
  }

  const response = await authenticatedAtlasApiRequest<unknown>(
    `/admin/sports/providers/${encodedId(providerId, "provider id")}` +
      `/accounts/${encodedId(sourceId, "source id")}`,
    {
      method: "PATCH",
      cache: "no-store",
      body
    }
  );

  return mapProviderList(response);
}

export async function loadAdminSportsAccountConnection(
  providerId: string,
  sourceId: string
): Promise<AdminSportsConnection> {
  const response = await authenticatedAtlasApiRequest<unknown>(
    `/admin/sports/providers/${encodedId(providerId, "provider id")}` +
      `/accounts/${encodedId(sourceId, "source id")}/connection`,
    {
      method: "GET",
      cache: "no-store"
    }
  );

  return mapConnection(response);
}

export async function testAdminSportsAccountConnection(
  providerId: string,
  sourceId: string
): Promise<AdminSportsConnectionTest> {
  const response = await authenticatedAtlasApiRequest<unknown>(
    `/admin/sports/providers/${encodedId(providerId, "provider id")}` +
      `/accounts/${encodedId(sourceId, "source id")}/test-connection`,
    {
      method: "POST",
      cache: "no-store"
    }
  );

  return mapConnectionTest(response);
}

export async function replaceAdminSportsAccountCredentials(
  providerId: string,
  sourceId: string,
  input: UpdateAdminSportsCredentialsInput
): Promise<AdminSportsConnection> {
  const body: Record<string, unknown> = {};

  if (input.serverUrl !== undefined) body.server_url = input.serverUrl;
  if (input.username !== undefined) body.username = input.username;
  if (input.password !== undefined) body.password = input.password;

  if (Object.keys(body).length === 0) {
    throw new Error("At least one provider credential field is required.");
  }

  const response = await authenticatedAtlasApiRequest<unknown>(
    `/admin/sports/providers/${encodedId(providerId, "provider id")}` +
      `/accounts/${encodedId(sourceId, "source id")}/credentials`,
    {
      method: "PATCH",
      cache: "no-store",
      body
    }
  );

  return mapConnection(response);
}

export async function createAdminSportsProviderAccount(
  providerId: string,
  input: CreateAdminSportsProviderAccountInput
): Promise<readonly AdminSportsProvider[]> {
  const response = await authenticatedAtlasApiRequest<unknown>(
    `/admin/sports/providers/${encodedId(providerId, "provider id")}/accounts`,
    {
      method: "POST",
      cache: "no-store",
      body: {
        source_id: requiredString(input.sourceId, "source id"),
        provider_display_name: requiredString(input.providerDisplayName, "provider display name"),
        account_display_name: requiredString(input.accountDisplayName, "account display name"),
        server_url: requiredString(input.serverUrl, "provider server URL"),
        username: requiredString(input.username, "provider username"),
        password: requiredString(input.password, "provider password"),
        max_connections: positiveInteger(input.maxConnections, "provider max connections"),
        priority: nonNegativeInteger(input.priority, "provider priority")
      }
    }
  );

  return mapProviderList(response);
}

export async function removeAdminSportsProviderAccount(
  providerId: string,
  sourceId: string
): Promise<boolean> {
  const response = await authenticatedAtlasApiRequest<unknown>(
    `/admin/sports/providers/${encodedId(providerId, "provider id")}` +
      `/accounts/${encodedId(sourceId, "source id")}`,
    {
      method: "DELETE",
      cache: "no-store"
    }
  );

  assertPublicSafe(response);

  const item = record(response, "provider account removal") as unknown as RemoveTransport;

  if (item.removed !== true) {
    throw new Error("Provider account removal was not confirmed.");
  }

  const returnedSourceId = requiredString(item.source_id, "removed source id");

  if (returnedSourceId !== requiredString(sourceId, "source id")) {
    throw new Error("Provider account removal returned the wrong source.");
  }

  return true;
}
