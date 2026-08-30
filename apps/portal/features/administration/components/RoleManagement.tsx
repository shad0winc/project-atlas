"use client";

import { useState } from "react";
import { usePermission } from "../../../lib/authorization";
import type { AdminRole } from "../api/roles";
import { useAdminRoles } from "../hooks/use-admin-roles";

function PermissionChoices({ permissions, selected, onChange, disabled }: Readonly<{
  permissions: readonly string[];
  selected: readonly string[];
  onChange: (permissions: readonly string[]) => void;
  disabled: boolean;
}>): React.ReactElement {
  const selectedSet = new Set(selected);
  return (
    <fieldset disabled={disabled}>
      <legend>Permissions</legend>
      <div className="role-permission-grid">
        {permissions.map((permission) => (
          <label key={permission}>
            <input
              checked={selectedSet.has(permission)}
              onChange={(event) => onChange(event.target.checked
                ? [...selected, permission]
                : selected.filter((item) => item !== permission))}
              type="checkbox"
            />
            {permission}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function RoleEditor({ role, permissions, canUpdate, canDelete, busy, onUpdate, onDelete }: Readonly<{
  role: AdminRole;
  permissions: readonly string[];
  canUpdate: boolean;
  canDelete: boolean;
  busy: boolean;
  onUpdate: (input: Readonly<{ displayName: string; description: string; permissions: readonly string[]; assignable: boolean }>) => Promise<boolean>;
  onDelete: () => Promise<boolean>;
}>): React.ReactElement {
  const [displayName, setDisplayName] = useState(role.displayName);
  const [description, setDescription] = useState(role.description);
  const [selectedPermissions, setSelectedPermissions] = useState<readonly string[]>(role.permissions);
  const [assignable, setAssignable] = useState(role.assignable);
  const editable = !role.protected && canUpdate;

  return (
    <article className="card administration-card role-management-card">
      <p className="portal-page-eyebrow">{role.protected ? "Built-in role" : "Custom role"}</p>
      <h4>{role.displayName}</h4>
      <p><code>{role.name}</code></p>
      {role.protected ? (
        <>
          <p>{role.description}</p>
          <p>Assignable: {role.assignable ? "Yes" : "No"}</p>
          <p>Permissions: {role.permissions.join(", ") || "None"}</p>
        </>
      ) : (
        <>
          <label>Display name<input disabled={!editable || busy} onChange={(e) => setDisplayName(e.target.value)} value={displayName} /></label>
          <label>Description<textarea disabled={!editable || busy} onChange={(e) => setDescription(e.target.value)} value={description} /></label>
          <label><input checked={assignable} disabled={!editable || busy} onChange={(e) => setAssignable(e.target.checked)} type="checkbox" /> Assignable to users</label>
          <PermissionChoices disabled={!editable || busy} onChange={setSelectedPermissions} permissions={permissions} selected={selectedPermissions} />
          {editable ? <button disabled={busy} onClick={() => void onUpdate({ displayName, description, permissions: selectedPermissions, assignable })} type="button">Save role</button> : null}
          {canDelete ? <button disabled={busy} onClick={() => void onDelete()} type="button">Delete role</button> : null}
        </>
      )}
    </article>
  );
}

export function RoleManagement(): React.ReactElement | null {
  const { can } = usePermission();
  const canRead = can("roles.read");
  const canCreate = can("roles.create");
  const canUpdate = can("roles.update");
  const canDelete = can("roles.delete");
  const { state, refresh, mutationError, busyKey, createRole, updateRole, removeRole } = useAdminRoles(canRead);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedPermissions, setSelectedPermissions] = useState<readonly string[]>([]);
  const [assignable, setAssignable] = useState(true);

  // Hook stays unconditional; enabled=false prevents unauthorized catalog reads.
  if (!canRead) return null;
  if (state.status === "loading") return <section aria-busy="true"><p>Loading roles and permissions…</p></section>;
  if (state.status === "error") return <section role="alert"><h3>Role management unavailable</h3><p>{state.error.message}</p><button onClick={refresh} type="button">Try again</button></section>;

  return (
    <section aria-labelledby="role-management-title" className="role-management">
      <div className="administration-surface-heading">
        <h3 id="role-management-title">Roles and permissions</h3>
        <p>Built-in service roles are protected. Custom roles can combine supported Atlas permissions.</p>
        {canCreate ? <button onClick={() => setShowCreate((value) => !value)} type="button">{showCreate ? "Cancel new role" : "Create role"}</button> : null}
      </div>
      {mutationError ? <section role="alert"><h4>Role action failed</h4><p>{mutationError.message}</p></section> : null}
      {showCreate ? (
        <form className="card administration-card role-management-card" onSubmit={(event) => {
          event.preventDefault();
          void createRole({ name, displayName, description, permissions: selectedPermissions, assignable }).then((created) => {
            if (created) { setShowCreate(false); setName(""); setDisplayName(""); setDescription(""); setSelectedPermissions([]); setAssignable(true); }
          });
        }}>
          <h4>Create custom role</h4>
          <label>Role name<input onChange={(e) => setName(e.target.value)} required value={name} /></label>
          <label>Display name<input onChange={(e) => setDisplayName(e.target.value)} required value={displayName} /></label>
          <label>Description<textarea onChange={(e) => setDescription(e.target.value)} value={description} /></label>
          <label><input checked={assignable} onChange={(e) => setAssignable(e.target.checked)} type="checkbox" /> Assignable to users</label>
          <PermissionChoices disabled={busyKey === "role:create"} onChange={setSelectedPermissions} permissions={state.catalog.permissions} selected={selectedPermissions} />
          <button disabled={busyKey === "role:create"} type="submit">{busyKey === "role:create" ? "Creating…" : "Create role"}</button>
        </form>
      ) : null}
      <div className="administration-grid">
        {state.catalog.roles.map((role) => <RoleEditor
          busy={busyKey === `role:${role.name}`}
          canDelete={!role.protected && canDelete}
          canUpdate={canUpdate}
          key={role.name}
          onDelete={() => removeRole(role.name)}
          onUpdate={(input) => updateRole(role.name, input)}
          permissions={state.catalog.permissions}
          role={role}
        />)}
      </div>
    </section>
  );
}
