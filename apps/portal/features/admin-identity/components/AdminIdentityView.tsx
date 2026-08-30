"use client";

import { useState } from "react";

import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";
import type { AdminInvitation, AdminUser } from "../api/admin-identity";
import { useAdminIdentity } from "../hooks/use-admin-identity";

function rolesLabel(user: AdminUser): string {
  return user.roles.length ? user.roles.join(", ") : "No roles";
}

function InvitationRow({
  invitation,
  canRevoke,
  busy,
  onRevoke
}: Readonly<{
  invitation: AdminInvitation;
  canRevoke: boolean;
  busy: boolean;
  onRevoke: () => void;
}>): React.ReactElement {
  return (
    <article className="card admin-identity-card">
      <p className="portal-page-eyebrow">{invitation.status}</p>
      <h4>{invitation.email ?? "Invitation without email"}</h4>
      <p>Role: {invitation.role}</p>
      <p>Invitation ID: {invitation.inviteId}</p>
      {canRevoke && invitation.status === "pending" ? (
        <button disabled={busy} onClick={onRevoke} type="button">
          {busy ? "Revoking…" : "Revoke invitation"}
        </button>
      ) : null}
    </article>
  );
}

function UserDetail({
  user,
  canUpdate,
  canAssignRoles,
  busy,
  onClose,
  onUpdate
}: Readonly<{
  user: AdminUser;
  canUpdate: boolean;
  canAssignRoles: boolean;
  busy: boolean;
  onClose: () => void;
  onUpdate: (
    updates: Readonly<{ status?: string; roles?: readonly string[] }>
  ) => Promise<boolean>;
}>): React.ReactElement {
  const [roles, setRoles] = useState(user.roles.join(", "));


  const nextStatus = user.status === "active" ? "disabled" : "active";

  return (
    <section aria-label={`User detail for ${user.displayName}`} className="card admin-identity-card">
      <p className="portal-page-eyebrow">User detail</p>
      <h3>{user.displayName}</h3>
      <p>Username: {user.username}</p>
      <p>Status: {user.status}</p>
      <p>Roles: {rolesLabel(user)}</p>

      {canUpdate ? (
        <button
          disabled={busy}
          onClick={() => void onUpdate({ status: nextStatus })}
          type="button"
        >
          {nextStatus === "disabled" ? "Disable user" : "Enable user"}
        </button>
      ) : null}

      {canAssignRoles ? (
        <div>
          <label htmlFor="admin-user-roles">Roles</label>
          <input
            id="admin-user-roles"
            onChange={(event) => setRoles(event.target.value)}
            value={roles}
          />
          <button
            disabled={busy}
            onClick={() => {
              const normalized = roles
                .split(",")
                .map((role) => role.trim())
                .filter(Boolean);
              void onUpdate({ roles: normalized });
            }}
            type="button"
          >
            Save roles
          </button>
        </div>
      ) : null}

      <button onClick={onClose} type="button">Close user detail</button>
    </section>
  );
}

export function AdminIdentityView(): React.ReactElement {
  const { can } = usePermission();
  const {
    state,
    refresh,
    selectedUser,
    detailLoading,
    inspectUser,
    clearSelectedUser,
    mutateUser,
    createInvitation,
    revokeInvitation,
    mutationError,
    createdToken,
    clearCreatedToken,
    busyKey
  } = useAdminIdentity();

  const [showInvitationForm, setShowInvitationForm] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<"user" | "admin">("user");
  const [days, setDays] = useState("7");
  const [invitationCreated, setInvitationCreated] = useState(false);

  const canCreate = can(ATLAS_PERMISSIONS.usersCreate);
  const canUpdate = can(ATLAS_PERMISSIONS.usersUpdate);
  const canAssignRoles = can(ATLAS_PERMISSIONS.rolesAssign);

  if (state.status === "loading") {
    return <section aria-busy="true"><p>Loading users and invitations…</p></section>;
  }

  if (state.status === "error") {
    return (
      <section role="alert">
        <h3>Administrator identity data unavailable</h3>
        <p>{state.error.message}</p>
        <button onClick={refresh} type="button">Try again</button>
      </section>
    );
  }

  return (
    <div>
      {mutationError ? (
        <section role="alert">
          <h3>Administrator action failed</h3>
          <p>{mutationError.message}</p>
        </section>
      ) : null}

      <section aria-labelledby="user-accounts-title">
        <h3 id="user-accounts-title">User accounts</h3>
        {state.users.length ? (
          <div>
            {state.users.map((user) => (
              <article className="card admin-identity-card" key={user.userId}>
                <h4>{user.displayName}</h4>
                <p>{user.username}</p>
                <p>Status: {user.status}</p>
                <p>Roles: {rolesLabel(user)}</p>
                <button
                  disabled={detailLoading}
                  onClick={() => void inspectUser(user.userId)}
                  type="button"
                >
                  View {user.displayName}
                </button>
              </article>
            ))}
          </div>
        ) : <p>No Atlas users were returned.</p>}
      </section>

      {selectedUser ? (
        <UserDetail
          key={selectedUser.userId}
          busy={busyKey === `user:${selectedUser.userId}`}
          canAssignRoles={canAssignRoles}
          canUpdate={canUpdate}
          onClose={clearSelectedUser}
          onUpdate={(updates) => mutateUser(selectedUser.userId, updates)}
          user={selectedUser}
        />
      ) : detailLoading ? <p aria-busy="true">Loading user detail…</p> : null}

      <section aria-labelledby="invitations-title">
        <div>
          <h3 id="invitations-title">Invitations</h3>
          {canCreate ? (
            <button
              onClick={() => {
                setShowInvitationForm(true);
                setInvitationCreated(false);
                clearCreatedToken();
              }}
              type="button"
            >
              Create invitation
            </button>
          ) : null}
        </div>

        {showInvitationForm ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void createInvitation({
                ...(email.trim() ? { email: email.trim() } : {}),
                role,
                days: Number.parseInt(days, 10)
              }).then((created) => {
                if (created) {
                  setInvitationCreated(true);
                  setShowInvitationForm(false);
                }
              });
            }}
          >
            <div>
              <label htmlFor="admin-invitation-email">Email</label>
              <input
                id="admin-invitation-email"
                onChange={(event) => setEmail(event.target.value)}
                type="email"
                value={email}
              />
            </div>
            <div>
              <label htmlFor="admin-invitation-role">Role</label>
              <select
                id="admin-invitation-role"
                onChange={(event) => setRole(event.target.value as "user" | "admin")}
                value={role}
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label htmlFor="admin-invitation-days">Expires in days</label>
              <input
                id="admin-invitation-days"
                min="1"
                onChange={(event) => setDays(event.target.value)}
                type="number"
                value={days}
              />
            </div>
            <button disabled={busyKey === "invitation:create"} type="submit">
              {busyKey === "invitation:create" ? "Creating…" : "Create invitation"}
            </button>
            <button onClick={() => setShowInvitationForm(false)} type="button">Cancel</button>
          </form>
        ) : null}

        {invitationCreated ? (
          <section role="status">
            <h4>Invitation created</h4>
            <p>Copy this invitation token now. Atlas discloses the token only at creation.</p>
            {createdToken ? (
              <label>
                Invitation token
                <input readOnly value={createdToken} />
              </label>
            ) : null}
          </section>
        ) : null}

        {state.invitations.length ? (
          <div>
            {state.invitations.map((invitation) => (
              <InvitationRow
                busy={busyKey === `invitation:${invitation.inviteId}`}
                canRevoke={canUpdate}
                invitation={invitation}
                key={invitation.inviteId}
                onRevoke={() => void revokeInvitation(invitation.inviteId)}
              />
            ))}
          </div>
        ) : <p>No invitations have been issued.</p>}
      </section>
    </div>
  );
}
