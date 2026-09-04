"use client";

import { useState } from "react";
import { Card } from "../../../components/ui/Card";
import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";
import { useAdminLiveSessions } from "../hooks/use-admin-live-sessions";

function positiveDraft(value: string): number | null {
  if (!/^[1-9][0-9]*$/.test(value)) return null;
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) ? parsed : null;
}

function secondsLabel(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  return remainder === 0 ? `${minutes}m` : `${minutes}m ${remainder}s`;
}

export function LiveSessionManagement(): React.ReactElement | null {
  const { can } = usePermission();
  const canManage = can(ATLAS_PERMISSIONS.liveSessionsManage);
  const {
    state,
    refresh,
    mutationError,
    busyKey,
    setDefaultLimit,
    setUserOverride,
    clearUserOverride
  } = useAdminLiveSessions(canManage);

  const [defaultDraft, setDefaultDraft] = useState<string | null>(null);
  const [userDrafts, setUserDrafts] = useState<Record<string, string>>({});

  if (!canManage) return null;

  if (state.status === "loading") {
    return (
      <section aria-labelledby="live-session-management-title" className="live-session-management">
        <h3 id="live-session-management-title">Live-session concurrency</h3>
        <p>Loading Live-session policy and active-session state…</p>
      </section>
    );
  }

  if (state.status === "error") {
    return (
      <section aria-labelledby="live-session-management-title" className="live-session-management">
        <h3 id="live-session-management-title">Live-session concurrency</h3>
        <p role="alert">{state.error.message}</p>
        <button className="button button--secondary" onClick={refresh} type="button">
          Try again
        </button>
      </section>
    );
  }

  const defaultValue = defaultDraft ?? String(state.policy.defaultLimit);
  const defaultLimit = positiveDraft(defaultValue);

  return (
    <section aria-labelledby="live-session-management-title" className="live-session-management">
      <div className="administration-surface-heading">
        <h3 id="live-session-management-title">Live-session concurrency</h3>
        <p>
          Control how many simultaneous Live sessions each Atlas user may start. Lowering a
          limit does not terminate sessions already in progress; it blocks additional sessions.
        </p>
      </div>

      {mutationError ? <p role="alert">{mutationError.message}</p> : null}

      <Card className="live-session-policy-card">
        <div>
          <p className="portal-page-eyebrow">Global policy</p>
          <h4>Default Live-session limit</h4>
          <p>
            Users without an explicit override inherit this value. Session heartbeat TTL:{" "}
            {state.policy.ttlSeconds} seconds.
          </p>
        </div>

        <form
          className="live-session-limit-form"
          onSubmit={(event) => {
            event.preventDefault();
            if (defaultLimit === null) return;

            void setDefaultLimit(defaultLimit).then((saved) => {
              if (saved) setDefaultDraft(null);
            });
          }}
        >
          <label>
            Default limit
            <input
              aria-label="Default Live-session limit"
              disabled={busyKey !== null}
              inputMode="numeric"
              min={1}
              onChange={(event) => setDefaultDraft(event.target.value)}
              type="number"
              value={defaultValue}
            />
          </label>
          <button
            className="button button--primary"
            disabled={busyKey !== null || defaultLimit === null}
            type="submit"
          >
            {busyKey === "default" ? "Saving…" : "Save default"}
          </button>
          <button
            className="button button--secondary"
            disabled={busyKey !== null}
            onClick={refresh}
            type="button"
          >
            Refresh
          </button>
        </form>
      </Card>

      <div className="live-session-user-grid">
        {state.policy.users.map((user) => {
          const draft = userDrafts[user.userId] ?? String(user.effectiveLimit);
          const parsedDraft = positiveDraft(draft);
          const userBusy = busyKey === `user:${user.userId}`;

          return (
            <Card className="live-session-user-card" key={user.userId}>
              <div className="live-session-user-heading">
                <div>
                  <p className="portal-page-eyebrow">{user.username}</p>
                  <h4>{user.displayName}</h4>
                </div>
                <strong>{user.activeCount} active / {user.effectiveLimit} allowed</strong>
              </div>

              <p>
                {user.overrideLimit === null
                  ? `Using global default (${state.policy.defaultLimit}).`
                  : `Explicit override: ${user.overrideLimit}.`}
              </p>

              <div className="live-session-user-controls">
                <label>
                  User limit
                  <input
                    aria-label={`Live-session limit for ${user.displayName}`}
                    disabled={busyKey !== null}
                    inputMode="numeric"
                    min={1}
                    onChange={(event) =>
                      setUserDrafts((drafts) => ({
                        ...drafts,
                        [user.userId]: event.target.value
                      }))
                    }
                    type="number"
                    value={draft}
                  />
                </label>

                <button
                  className="button button--primary"
                  disabled={busyKey !== null || parsedDraft === null}
                  onClick={() => {
                    if (parsedDraft === null) return;

                    void setUserOverride(user.userId, parsedDraft).then((saved) => {
                      if (!saved) return;

                      setUserDrafts((drafts) => {
                        const next = { ...drafts };
                        delete next[user.userId];
                        return next;
                      });
                    });
                  }}
                  type="button"
                >
                  {userBusy ? "Saving…" : "Save override"}
                </button>

                <button
                  className="button button--secondary"
                  disabled={busyKey !== null || user.overrideLimit === null}
                  onClick={() => {
                    void clearUserOverride(user.userId).then((cleared) => {
                      if (!cleared) return;

                      setUserDrafts((drafts) => {
                        const next = { ...drafts };
                        delete next[user.userId];
                        return next;
                      });
                    });
                  }}
                  type="button"
                >
                  Default
                </button>
              </div>

              <details>
                <summary>
                  {user.activeCount === 1 ? "1 active session" : `${user.activeCount} active sessions`}
                </summary>
                {user.sessions.length === 0 ? (
                  <p>No active Live sessions.</p>
                ) : (
                  <ul className="live-session-detail-list">
                    {user.sessions.map((session) => (
                      <li key={session.sessionId}>
                        <strong>{session.targetId}</strong>
                        <span>Session {session.sessionId}</span>
                        <span>Age {secondsLabel(session.ageSeconds)}</span>
                        <span>Last heartbeat {secondsLabel(session.heartbeatAgeSeconds)} ago</span>
                      </li>
                    ))}
                  </ul>
                )}
              </details>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
