"use client";

import { useState } from "react";

import { Card } from "../../../components/ui/Card";
import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";
import type {
  CreateAdminSportsProviderAccountInput,
  UpdateAdminSportsCredentialsInput
} from "../api/provider-accounts";
import { useAdminSportsProviders } from "../hooks/use-admin-sports-providers";

function textValue(data: FormData, name: string): string | null {
  const value = data.get(name);

  if (typeof value !== "string") return null;

  const normalized = value.trim();

  return normalized === "" ? null : normalized;
}

function rawSecretValue(data: FormData, name: string): string | null {
  const value = data.get(name);

  if (typeof value !== "string") return null;

  return value.trim() === "" ? null : value;
}

function positiveIntegerValue(data: FormData, name: string): number | null {
  const value = textValue(data, name);

  if (value === null || !/^[1-9][0-9]*$/.test(value)) {
    return null;
  }

  const parsed = Number(value);

  return Number.isSafeInteger(parsed) ? parsed : null;
}

function nonNegativeIntegerValue(data: FormData, name: string): number | null {
  const value = textValue(data, name);

  if (value === null || !/^[0-9]+$/.test(value)) {
    return null;
  }

  const parsed = Number(value);

  return Number.isSafeInteger(parsed) ? parsed : null;
}

export function ProviderAccountManagement(): React.ReactElement | null {
  const { can } = usePermission();
  const canManage = can(ATLAS_PERMISSIONS.sportsProvidersManage);

  const {
    state,
    refresh,
    mutationError,
    busyKey,
    connections,
    connectionTests,
    renameProvider,
    updateAccount,
    setAccountEnabled,
    loadConnection,
    testConnection,
    replaceCredentials,
    createAccount,
    removeAccount
  } = useAdminSportsProviders(canManage);

  const [showCreate, setShowCreate] = useState(false);
  const [removeArmed, setRemoveArmed] = useState<string | null>(null);

  if (!canManage) return null;

  if (state.status === "loading") {
    return (
      <section aria-busy="true" aria-labelledby="provider-account-management-title">
        <h3 id="provider-account-management-title">Sports provider accounts</h3>
        <p>Loading provider accounts and capacity…</p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section aria-labelledby="provider-account-management-title" role="alert">
        <h3 id="provider-account-management-title">Sports provider accounts</h3>
        <p>{state.error.message}</p>
        <button className="button button--secondary" onClick={refresh} type="button">
          Try again
        </button>
      </section>
    );
  }

  const poolBySource = new Map(
    state.resourcePool.accounts.map((account) => [account.sourceId, account])
  );

  return (
    <section aria-labelledby="provider-account-management-title" className="administration-surface">
      <div className="administration-surface-heading">
        <div>
          <p className="portal-page-eyebrow">Sports administration</p>
          <h3 id="provider-account-management-title">Sports provider accounts</h3>
          <p>
            Manage Atlas provider identities, upstream capacity, connection health, and pool
            participation. Stored credentials and provider URLs are never displayed.
          </p>
        </div>

        <div>
          <button
            className="button button--secondary"
            disabled={busyKey !== null}
            onClick={refresh}
            type="button"
          >
            Refresh
          </button>{" "}
          <button
            className="button button--primary"
            disabled={busyKey !== null}
            onClick={() => setShowCreate((current) => !current)}
            type="button"
          >
            {showCreate ? "Cancel new account" : "Add provider account"}
          </button>
        </div>
      </div>

      {mutationError ? (
        <div role="alert">
          <strong>Provider action failed.</strong>
          <p>{mutationError.message}</p>
        </div>
      ) : null}

      <Card className="administration-card">
        <p className="portal-page-eyebrow">Shared upstream resource pool</p>
        <h4>
          {state.resourcePool.active} active / {state.resourcePool.totalCapacity} enabled capacity
        </h4>
        <p>
          {state.resourcePool.available} connection
          {state.resourcePool.available === 1 ? "" : "s"} currently available.
        </p>
      </Card>

      {showCreate ? (
        <form
          className="card administration-card"
          onSubmit={(event) => {
            event.preventDefault();

            const form = event.currentTarget;
            const data = new FormData(form);

            const providerId = textValue(data, "providerId");
            const sourceId = textValue(data, "sourceId");
            const providerDisplayName = textValue(data, "providerDisplayName");
            const accountDisplayName = textValue(data, "accountDisplayName");
            const serverUrl = textValue(data, "serverUrl");
            const username = textValue(data, "username");
            const password = rawSecretValue(data, "password");
            const maxConnections = positiveIntegerValue(data, "maxConnections");
            const priority = nonNegativeIntegerValue(data, "priority");

            if (
              providerId === null ||
              sourceId === null ||
              providerDisplayName === null ||
              accountDisplayName === null ||
              serverUrl === null ||
              username === null ||
              password === null ||
              maxConnections === null ||
              priority === null
            ) {
              return;
            }

            const input: CreateAdminSportsProviderAccountInput = {
              sourceId,
              providerDisplayName,
              accountDisplayName,
              serverUrl,
              username,
              password,
              maxConnections,
              priority
            };

            void createAccount(providerId, input).then((created) => {
              if (!created) return;

              form.reset();
              setShowCreate(false);
            });
          }}
        >
          <p className="portal-page-eyebrow">Secure account creation</p>
          <h4>Add provider account</h4>
          <p>
            New accounts are created disabled. For an existing provider, its display name must
            exactly match the current Atlas provider display name.
          </p>

          <label>
            Provider ID
            <input autoComplete="off" disabled={busyKey !== null} name="providerId" required />
          </label>

          <label>
            Provider display name
            <input
              autoComplete="off"
              disabled={busyKey !== null}
              name="providerDisplayName"
              required
            />
          </label>

          <label>
            Source ID
            <input autoComplete="off" disabled={busyKey !== null} name="sourceId" required />
          </label>

          <label>
            Account display name
            <input
              autoComplete="off"
              disabled={busyKey !== null}
              name="accountDisplayName"
              required
            />
          </label>

          <label>
            Server URL
            <input
              autoComplete="off"
              disabled={busyKey !== null}
              name="serverUrl"
              required
              type="url"
            />
          </label>

          <label>
            Username
            <input autoComplete="off" disabled={busyKey !== null} name="username" required />
          </label>

          <label>
            Password
            <input
              autoComplete="new-password"
              disabled={busyKey !== null}
              name="password"
              required
              type="password"
            />
          </label>

          <label>
            Max connections
            <input
              defaultValue="1"
              disabled={busyKey !== null}
              inputMode="numeric"
              min={1}
              name="maxConnections"
              required
              type="number"
            />
          </label>

          <label>
            Priority
            <input
              defaultValue="100"
              disabled={busyKey !== null}
              inputMode="numeric"
              min={0}
              name="priority"
              required
              type="number"
            />
          </label>

          <button className="button button--primary" disabled={busyKey !== null} type="submit">
            {busyKey === "account:create" ? "Creating…" : "Create disabled account"}
          </button>
        </form>
      ) : null}

      {state.providers.length === 0 ? (
        <Card className="administration-card">
          <h4>No provider accounts configured</h4>
          <p>Add a provider account to establish an Atlas-managed upstream connection.</p>
        </Card>
      ) : (
        <div className="administration-grid">
          {state.providers.map((provider) => (
            <Card className="administration-card" key={provider.providerId}>
              <p className="portal-page-eyebrow">Provider</p>
              <h4>{provider.displayName}</h4>
              <p>
                Stable ID: <code>{provider.providerId}</code>
              </p>
              <p>
                {provider.enabledAccountCount} enabled / {provider.accountCount} configured accounts
              </p>
              <p>
                Enabled capacity: {provider.enabledMaxConnections} / configured{" "}
                {provider.configuredMaxConnections}
              </p>

              <form
                onSubmit={(event) => {
                  event.preventDefault();

                  const data = new FormData(event.currentTarget);

                  const displayName = textValue(data, "providerDisplayName");

                  if (displayName === null) return;

                  void renameProvider(provider.providerId, displayName);
                }}
              >
                <label>
                  Provider display name
                  <input
                    defaultValue={provider.displayName}
                    disabled={busyKey !== null}
                    name="providerDisplayName"
                    required
                  />
                </label>

                <button
                  className="button button--secondary"
                  disabled={busyKey !== null}
                  type="submit"
                >
                  {busyKey === `provider:${provider.providerId}:rename`
                    ? "Saving…"
                    : "Save provider name"}
                </button>
              </form>

              {provider.accounts.map((account) => {
                const pool = poolBySource.get(account.sourceId);

                const connection = connections[account.sourceId];

                const connectionTest = connectionTests[account.sourceId];

                const active = pool?.active ?? 0;
                const removalBlocked = account.enabled || active > 0;

                return (
                  <article className="card administration-card" key={account.sourceId}>
                    <p className="portal-page-eyebrow">
                      {account.enabled ? "Enabled account" : "Disabled account"}
                    </p>
                    <h5>{account.accountDisplayName}</h5>

                    <p>
                      Source ID: <code>{account.sourceId}</code>
                    </p>
                    <p>Source label: {account.displayName}</p>
                    <p>Backend configured: {account.backendConfigured ? "Yes" : "No"}</p>
                    <p>
                      Priority: {account.priority} <span>(read-only)</span>
                    </p>
                    <p>
                      Capacity: {account.maxConnections}; active: {active}; available:{" "}
                      {pool?.available ?? 0}
                    </p>
                    <p>
                      Kind: {account.kind}; trust: {account.trustClass}
                    </p>
                    <p>Expiration: {account.expiresAt ?? "Not reported"}</p>

                    <button
                      className={
                        account.enabled ? "button button--secondary" : "button button--primary"
                      }
                      disabled={busyKey !== null}
                      onClick={() =>
                        void setAccountEnabled(
                          provider.providerId,
                          account.sourceId,
                          !account.enabled
                        )
                      }
                      type="button"
                    >
                      {busyKey === `account:${account.sourceId}:enabled`
                        ? "Saving…"
                        : account.enabled
                          ? "Disable pool participation"
                          : "Enable pool participation"}
                    </button>

                    <details>
                      <summary>Account metadata</summary>

                      <form
                        onSubmit={(event) => {
                          event.preventDefault();

                          const data = new FormData(event.currentTarget);

                          const accountDisplayName = textValue(data, "accountDisplayName");

                          const maxConnections = positiveIntegerValue(data, "maxConnections");

                          if (accountDisplayName === null || maxConnections === null) {
                            return;
                          }

                          void updateAccount(provider.providerId, account.sourceId, {
                            accountDisplayName,
                            maxConnections
                          });
                        }}
                      >
                        <label>
                          Account display name
                          <input
                            defaultValue={account.accountDisplayName}
                            disabled={busyKey !== null}
                            name="accountDisplayName"
                            required
                          />
                        </label>

                        <label>
                          Max connections
                          <input
                            defaultValue={account.maxConnections}
                            disabled={busyKey !== null}
                            inputMode="numeric"
                            min={1}
                            name="maxConnections"
                            required
                            type="number"
                          />
                        </label>

                        <p>Priority {account.priority} is fixed for this v1 editing surface.</p>

                        <button
                          className="button button--secondary"
                          disabled={busyKey !== null}
                          type="submit"
                        >
                          {busyKey === `account:${account.sourceId}:metadata`
                            ? "Saving…"
                            : "Save account metadata"}
                        </button>
                      </form>
                    </details>

                    <details>
                      <summary>Connection and credentials</summary>

                      <p>Stored connection values are write-only and are never shown in Portal.</p>

                      <div>
                        <button
                          className="button button--secondary"
                          disabled={busyKey !== null}
                          onClick={() => void loadConnection(provider.providerId, account.sourceId)}
                          type="button"
                        >
                          {busyKey === `account:${account.sourceId}:connection`
                            ? "Loading…"
                            : "Load safe connection status"}
                        </button>{" "}
                        <button
                          className="button button--secondary"
                          disabled={busyKey !== null}
                          onClick={() => void testConnection(provider.providerId, account.sourceId)}
                          type="button"
                        >
                          {busyKey === `account:${account.sourceId}:test`
                            ? "Testing…"
                            : "Test connection"}
                        </button>
                      </div>

                      {connection ? (
                        <div>
                          <p>Account type: {connection.accountType}</p>
                          <p>
                            Credentials configured:{" "}
                            {connection.credentialsConfigured ? "Yes" : "No"}
                          </p>
                          <p>Backend capacity: {connection.configuredMaxConnections}</p>
                          <p>Backend state: {connection.enabled ? "Enabled" : "Disabled"}</p>
                        </div>
                      ) : null}

                      {connectionTest ? (
                        <div role="status">
                          <p>Test result: {connectionTest.ok ? "Passed" : "Failed"}</p>
                          <p>Provider status: {connectionTest.status}</p>
                          <p>
                            Provider capacity:{" "}
                            {connectionTest.providerMaxConnections ?? "Not reported"}
                          </p>
                          <p>
                            Active upstream connections:{" "}
                            {connectionTest.activeConnections ?? "Not reported"}
                          </p>
                          <p>Provider expiration: {connectionTest.expiresAt ?? "Not reported"}</p>
                        </div>
                      ) : null}

                      <form
                        onSubmit={(event) => {
                          event.preventDefault();

                          const form = event.currentTarget;

                          const data = new FormData(form);

                          const serverUrl = textValue(data, "serverUrl");
                          const username = textValue(data, "username");
                          const password = rawSecretValue(data, "password");

                          const input: UpdateAdminSportsCredentialsInput = {};

                          if (serverUrl !== null) {
                            (
                              input as {
                                serverUrl?: string;
                              }
                            ).serverUrl = serverUrl;
                          }

                          if (username !== null) {
                            (
                              input as {
                                username?: string;
                              }
                            ).username = username;
                          }

                          if (password !== null) {
                            (
                              input as {
                                password?: string;
                              }
                            ).password = password;
                          }

                          if (serverUrl === null && username === null && password === null) {
                            return;
                          }

                          void replaceCredentials(
                            provider.providerId,
                            account.sourceId,
                            input
                          ).then((saved) => {
                            if (saved) form.reset();
                          });
                        }}
                      >
                        <fieldset disabled={busyKey !== null}>
                          <legend>Replace stored connection fields</legend>

                          <p>
                            Enter only values that should be replaced. Existing stored values stay
                            hidden.
                          </p>

                          <label>
                            New server URL
                            <input autoComplete="off" name="serverUrl" type="url" />
                          </label>

                          <label>
                            New username
                            <input autoComplete="off" name="username" />
                          </label>

                          <label>
                            New password
                            <input autoComplete="new-password" name="password" type="password" />
                          </label>

                          <button className="button button--secondary" type="submit">
                            {busyKey === `account:${account.sourceId}:credentials`
                              ? "Saving…"
                              : "Replace connection"}
                          </button>
                        </fieldset>
                      </form>
                    </details>

                    <details>
                      <summary>Remove account</summary>

                      {account.enabled ? (
                        <p>Disable pool participation before removal.</p>
                      ) : active > 0 ? (
                        <p>Removal is blocked while this account has active upstream leases.</p>
                      ) : removeArmed === account.sourceId ? (
                        <div>
                          <p>
                            Confirm removal of <strong>{account.accountDisplayName}</strong>. The
                            backend will perform its final dependency checks before deletion.
                          </p>
                          <button
                            className="button button--primary"
                            disabled={busyKey !== null}
                            onClick={() =>
                              void removeAccount(provider.providerId, account.sourceId).then(
                                (removed) => {
                                  if (removed) {
                                    setRemoveArmed(null);
                                  }
                                }
                              )
                            }
                            type="button"
                          >
                            {busyKey === `account:${account.sourceId}:remove`
                              ? "Removing…"
                              : "Confirm removal"}
                          </button>{" "}
                          <button
                            className="button button--secondary"
                            disabled={busyKey !== null}
                            onClick={() => setRemoveArmed(null)}
                            type="button"
                          >
                            Cancel
                          </button>
                        </div>
                      ) : (
                        <button
                          className="button button--secondary"
                          disabled={busyKey !== null || removalBlocked}
                          onClick={() => setRemoveArmed(account.sourceId)}
                          type="button"
                        >
                          Remove account
                        </button>
                      )}
                    </details>
                  </article>
                );
              })}
            </Card>
          ))}
        </div>
      )}
    </section>
  );
}
