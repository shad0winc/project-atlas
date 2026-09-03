"use client";

import { useEffect, useState } from "react";

import { ATLAS_PERMISSIONS, usePermission } from "../../../lib/authorization";
import { loadAssignableRoleCatalog, type AssignableRole } from "../../administration/api/roles";
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
  profileBusy,
  passwordBusy,
  onClose,
  onUpdate,
  onSetPassword,
  assignableRoles
}: Readonly<{
  user: AdminUser;
  canUpdate: boolean;
  canAssignRoles: boolean;
  profileBusy: boolean;
  passwordBusy: boolean;
  assignableRoles: readonly AssignableRole[];
  onClose: () => void;
  onUpdate: (
    updates: Readonly<{
      displayName?: string;
      firstName?: string | null;
      lastName?: string | null;
      email?: string;
      discordAccount?: string | null;
      emailNotificationsEnabled?: boolean;
      discordNotificationsEnabled?: boolean;
      status?: string;
      roles?: readonly string[];
    }>
  ) => Promise<boolean>;
  onSetPassword: (
    newPassword: string
  ) => Promise<boolean>;
}>): React.ReactElement {
  const [displayName, setDisplayName] = useState(user.displayName);
  const [firstName, setFirstName] = useState(user.firstName ?? "");
  const [lastName, setLastName] = useState(user.lastName ?? "");
  const [email, setEmail] = useState(user.email ?? "");
  const [discordAccount, setDiscordAccount] = useState(
    user.discordAccount ?? ""
  );
  const [
    emailNotificationsEnabled,
    setEmailNotificationsEnabled
  ] = useState(user.emailNotificationsEnabled);
  const [
    discordNotificationsEnabled,
    setDiscordNotificationsEnabled
  ] = useState(user.discordNotificationsEnabled);
  const [roles, setRoles] = useState<readonly string[]>(user.roles);
  const [newPassword, setNewPassword] = useState("");

  const nextStatus =
    user.status === "active" ? "disabled" : "active";

  const profileValid =
    Boolean(displayName.trim()) &&
    Boolean(email.trim()) &&
    (
      !discordNotificationsEnabled ||
      Boolean(discordAccount.trim())
    );

  return (
    <section
      aria-label={`User detail for ${user.displayName}`}
      className="admin-identity-inline-detail"
    >
      <div className="admin-identity-detail-header">
        <div>
          <p className="portal-page-eyebrow">User detail</p>
          <h3>{user.displayName}</h3>
          <p>Status: {user.status}</p>
        </div>

        <button onClick={onClose} type="button">
          Close user detail
        </button>
      </div>

      <section
        aria-labelledby={`account-${user.userId}`}
        className="admin-identity-section"
      >
        <h4 id={`account-${user.userId}`}>Account</h4>

        <div className="admin-identity-field-grid">
          <label>
            Username
            <input
              readOnly
              value={user.username}
            />
          </label>

          <label>
            <span>Display Name <span aria-hidden="true">*</span></span>
            <input
              disabled={!canUpdate || profileBusy}
              onChange={(event) =>
                setDisplayName(event.target.value)
              }
              required
              value={displayName}
            />
          </label>

          <label>
            <span>Email Address <span aria-hidden="true">*</span></span>
            <input
              autoComplete="email"
              disabled={!canUpdate || profileBusy}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              required
              type="email"
              value={email}
            />
          </label>

          <label>
            First Name
            <input
              autoComplete="given-name"
              disabled={!canUpdate || profileBusy}
              onChange={(event) =>
                setFirstName(event.target.value)
              }
              value={firstName}
            />
          </label>

          <label>
            Last Name
            <input
              autoComplete="family-name"
              disabled={!canUpdate || profileBusy}
              onChange={(event) =>
                setLastName(event.target.value)
              }
              value={lastName}
            />
          </label>

          <label>
            Discord Account
            <input
              disabled={!canUpdate || profileBusy}
              onChange={(event) =>
                setDiscordAccount(event.target.value)
              }
              value={discordAccount}
            />
          </label>
        </div>

        {canUpdate ? (
          <button
            disabled={profileBusy || !profileValid}
            onClick={() =>
              void onUpdate({
                displayName: displayName.trim(),
                firstName: firstName.trim() || null,
                lastName: lastName.trim() || null,
                email: email.trim(),
                discordAccount:
                  discordAccount.trim() || null,
                emailNotificationsEnabled,
                discordNotificationsEnabled
              })
            }
            type="button"
          >
            {profileBusy ? "Saving account…" : "Save account"}
          </button>
        ) : null}
      </section>

      <section
        aria-labelledby={`notifications-${user.userId}`}
        className="admin-identity-section"
      >
        <h4 id={`notifications-${user.userId}`}>
          Notifications
        </h4>

        <label className="admin-identity-checkbox-row">
          <input
            checked={emailNotificationsEnabled}
            disabled={!canUpdate || profileBusy}
            onChange={(event) =>
              setEmailNotificationsEnabled(
                event.target.checked
              )
            }
            type="checkbox"
          />
          Email notifications
        </label>

        <label className="admin-identity-checkbox-row">
          <input
            checked={discordNotificationsEnabled}
            disabled={!canUpdate || profileBusy}
            onChange={(event) =>
              setDiscordNotificationsEnabled(
                event.target.checked
              )
            }
            type="checkbox"
          />
          Discord notifications
        </label>

        {discordNotificationsEnabled &&
        !discordAccount.trim() ? (
          <p role="alert">
            Add a Discord Account before enabling Discord
            notifications.
          </p>
        ) : null}
      </section>

      <section
        aria-labelledby={`access-${user.userId}`}
        className="admin-identity-section"
      >
        <h4 id={`access-${user.userId}`}>Access</h4>

        <p>Roles: {rolesLabel(user)}</p>

        {canUpdate ? (
          <button
            disabled={profileBusy}
            onClick={() =>
              void onUpdate({
                status: nextStatus
              })
            }
            type="button"
          >
            {nextStatus === "disabled"
              ? "Disable user"
              : "Enable user"}
          </button>
        ) : null}

        {canAssignRoles ? (
          <div>
            <fieldset disabled={profileBusy}>
              <legend>Roles</legend>

              {roles
                .filter(
                  (name) =>
                    !assignableRoles.some(
                      (role) => role.name === name
                    )
                )
                .map((name) => (
                  <p key={name}>
                    Retained protected/nonassignable role:{" "}
                    {name}
                  </p>
                ))}

              {assignableRoles.map((role) => (
                <label key={role.name}>
                  <input
                    checked={roles.includes(role.name)}
                    onChange={(event) =>
                      setRoles(
                        event.target.checked
                          ? [...roles, role.name]
                          : roles.filter(
                              (name) =>
                                name !== role.name
                            )
                      )
                    }
                    type="checkbox"
                  />
                  {role.displayName}
                </label>
              ))}
            </fieldset>

            <button
              disabled={profileBusy}
              onClick={() =>
                void onUpdate({
                  roles
                })
              }
              type="button"
            >
              Save roles
            </button>
          </div>
        ) : null}
      </section>

      {canUpdate ? (
        <section
          aria-labelledby={`security-${user.userId}`}
          className="admin-identity-section"
        >
          <h4 id={`security-${user.userId}`}>
            Security
          </h4>

          <label>
            New Password
            <input
              autoComplete="new-password"
              disabled={passwordBusy}
              onChange={(event) =>
                setNewPassword(event.target.value)
              }
              type="password"
              value={newPassword}
            />
          </label>

          <button
            disabled={
              passwordBusy ||
              !newPassword
            }
            onClick={() => {
              const passwordForSubmission = newPassword;
              setNewPassword("");

              void onSetPassword(
                passwordForSubmission
              );
            }}
            type="button"
          >
            {passwordBusy
              ? "Setting password…"
              : "Set New Password"}
          </button>

          <p>
            Password changes are applied through the linked
            Jellyfin identity. Atlas does not store the password.
          </p>
        </section>
      ) : null}
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
    createUser,
    setUserPassword,
    createInvitation,
    revokeInvitation,
    mutationError,
    createdToken,
    clearCreatedToken,
    busyKey
  } = useAdminIdentity();

  const [showUserForm, setShowUserForm] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [newDisplayName, setNewDisplayName] = useState("");
  const [newFirstName, setNewFirstName] = useState("");
  const [newLastName, setNewLastName] = useState("");
  const [newDiscordAccount, setNewDiscordAccount] = useState("");
  const [
    newEmailNotificationsEnabled,
    setNewEmailNotificationsEnabled
  ] = useState(false);
  const [
    newDiscordNotificationsEnabled,
    setNewDiscordNotificationsEnabled
  ] = useState(false);
  const [newUserRole, setNewUserRole] = useState("member");

  const [showInvitationForm, setShowInvitationForm] = useState(false);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [days, setDays] = useState("7");
  const [invitationCreated, setInvitationCreated] = useState(false);
  const [assignableRoles, setAssignableRoles] = useState<readonly AssignableRole[]>([]);

  const canCreate = can(ATLAS_PERMISSIONS.usersCreate);
  const canUpdate = can(ATLAS_PERMISSIONS.usersUpdate);
  const canAssignRoles = can(ATLAS_PERMISSIONS.rolesAssign);

  useEffect(() => {
    if (!canAssignRoles) return;
    const controller = new AbortController();
    loadAssignableRoleCatalog(controller.signal)
      .then((roles) => {
        setAssignableRoles(roles);
        if (roles.length) {
          setRole((currentRole) =>
            roles.some((item) => item.name === currentRole)
              ? currentRole
              : roles[0].name
          );

          setNewUserRole((currentRole) =>
            roles.some((item) => item.name === currentRole)
              ? currentRole
              : roles[0].name
          );
        }
      })
      .catch(() => setAssignableRoles([]));
    return () => controller.abort();
  }, [canAssignRoles]);

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
        <div>
          <h3 id="user-accounts-title">User accounts</h3>

          {canCreate && canAssignRoles ? (
            <button
              disabled={busyKey === "user:create"}
              onClick={() => setShowUserForm((visible) => !visible)}
              type="button"
            >
              {showUserForm ? "Cancel user creation" : "Create user"}
            </button>
          ) : null}
        </div>

        {showUserForm && canCreate && canAssignRoles ? (
          <form
            onSubmit={(event) => {
              event.preventDefault();

              const passwordForSubmission = newPassword;

              // Credentials must not remain in component state while the
              // network mutation is in flight or after it completes.
              setNewPassword("");

              void createUser({
                username: newUsername,
                displayName: newDisplayName,
                email: newEmail,
                password: passwordForSubmission,
                roles: [newUserRole],
                ...(newFirstName.trim()
                  ? { firstName: newFirstName }
                  : {}),
                ...(newLastName.trim()
                  ? { lastName: newLastName }
                  : {}),
                ...(newDiscordAccount.trim()
                  ? {
                      discordAccount:
                        newDiscordAccount
                    }
                  : {}),
                emailNotificationsEnabled:
                  newEmailNotificationsEnabled,
                discordNotificationsEnabled:
                  newDiscordNotificationsEnabled
              }).then((created) => {
                if (!created) return;

                setNewUsername("");
                setNewEmail("");
                setNewDisplayName("");
                setNewFirstName("");
                setNewLastName("");
                setNewDiscordAccount("");
                setNewEmailNotificationsEnabled(false);
                setNewDiscordNotificationsEnabled(false);
                setShowUserForm(false);
              });
            }}
          >
            <h4>Create Atlas user</h4>

            <p>
              Fields marked with <span aria-hidden="true">*</span> are required.
            </p>

            <div className="admin-identity-field-grid">
            <label>
              <span>Username <span aria-hidden="true">*</span></span>
              <input
                autoComplete="username"
                onChange={(event) => setNewUsername(event.target.value)}
                required
                value={newUsername}
              />
            </label>

            <label>
              <span>Email Address <span aria-hidden="true">*</span></span>
              <input
                autoComplete="email"
                onChange={(event) => setNewEmail(event.target.value)}
                required
                type="email"
                value={newEmail}
              />
            </label>

            <label>
              <span>Password <span aria-hidden="true">*</span></span>
              <input
                autoComplete="new-password"
                onChange={(event) => setNewPassword(event.target.value)}
                required
                type="password"
                value={newPassword}
              />
            </label>

            <label>
              <span>Display Name <span aria-hidden="true">*</span></span>
              <input
                onChange={(event) =>
                  setNewDisplayName(event.target.value)
                }
                required
                value={newDisplayName}
              />
            </label>

            <label>
              First name
              <input
                autoComplete="given-name"
                onChange={(event) => setNewFirstName(event.target.value)}
                value={newFirstName}
              />
            </label>

            <label>
              Last name
              <input
                autoComplete="family-name"
                onChange={(event) => setNewLastName(event.target.value)}
                value={newLastName}
              />
            </label>

            <label>
              Discord Account
              <input
                onChange={(event) =>
                  setNewDiscordAccount(
                    event.target.value
                  )
                }
                value={newDiscordAccount}
              />
            </label>

            <label>
              Initial role
              <select
                onChange={(event) => setNewUserRole(event.target.value)}
                required
                value={newUserRole}
              >
                {assignableRoles.map((assignableRole) => (
                  <option
                    key={assignableRole.name}
                    value={assignableRole.name}
                  >
                    {assignableRole.displayName}
                  </option>
                ))}
              </select>
            </label>
            </div>

            <fieldset>
              <legend>Notifications</legend>

              <label className="admin-identity-checkbox-row">
                <input
                  checked={newEmailNotificationsEnabled}
                  onChange={(event) =>
                    setNewEmailNotificationsEnabled(
                      event.target.checked
                    )
                  }
                  type="checkbox"
                />
                Email notifications
              </label>

              <label className="admin-identity-checkbox-row">
                <input
                  checked={newDiscordNotificationsEnabled}
                  onChange={(event) =>
                    setNewDiscordNotificationsEnabled(
                      event.target.checked
                    )
                  }
                  type="checkbox"
                />
                Discord notifications
              </label>
            </fieldset>

            {newDiscordNotificationsEnabled &&
            !newDiscordAccount.trim() ? (
              <p role="alert">
                Add a Discord Account before enabling Discord
                notifications.
              </p>
            ) : null}

            <button
              disabled={
                busyKey === "user:create" ||
                !newUsername.trim() ||
                !newDisplayName.trim() ||
                !newEmail.trim() ||
                !newPassword ||
                !newUserRole ||
                (
                  newDiscordNotificationsEnabled &&
                  !newDiscordAccount.trim()
                )
              }
              type="submit"
            >
              {busyKey === "user:create"
                ? "Creating user…"
                : "Create Atlas user"}
            </button>
          </form>
        ) : null}

        {state.users.length ? (
          <div>
            {state.users.map((user) => {
              const isSelected = selectedUser?.userId === user.userId;

              return (
                <article className="card admin-identity-card" key={user.userId}>
                  <h4>{user.displayName}</h4>
                  <p>{user.username}</p>
                  <p>Status: {user.status}</p>
                  <p>Roles: {rolesLabel(user)}</p>

                  {isSelected && selectedUser ? (
                    <UserDetail
                      assignableRoles={assignableRoles}
                      canAssignRoles={canAssignRoles}
                      canUpdate={canUpdate}
                      onClose={clearSelectedUser}
                      onSetPassword={(newPassword) =>
                        setUserPassword(
                          selectedUser.userId,
                          newPassword
                        )
                      }
                      onUpdate={(updates) =>
                        mutateUser(
                          selectedUser.userId,
                          updates
                        )
                      }
                      passwordBusy={
                        busyKey ===
                        `user-password:${selectedUser.userId}`
                      }
                      profileBusy={
                        busyKey ===
                        `user:${selectedUser.userId}`
                      }
                      user={selectedUser}
                    />
                  ) : (
                    <button
                      disabled={detailLoading}
                      onClick={() => void inspectUser(user.userId)}
                      type="button"
                    >
                      Manage {user.displayName}
                    </button>
                  )}
                </article>
              );
            })}
          </div>
        ) : <p>No Atlas users were returned.</p>}
      </section>

      {detailLoading && !selectedUser ? (
        <p aria-busy="true">Loading user detail…</p>
      ) : null}

      <section aria-labelledby="invitations-title">
        <div>
          <h3 id="invitations-title">Invitations</h3>
          {canCreate && canAssignRoles ? (
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
                disabled={!assignableRoles.length}
                onChange={(event) => setRole(event.target.value)}
                value={role}
              >
                {assignableRoles.map((item) => (
                  <option key={item.name} value={item.name}>{item.displayName}</option>
                ))}
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
            <button disabled={busyKey === "invitation:create" || !assignableRoles.length} type="submit">
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
