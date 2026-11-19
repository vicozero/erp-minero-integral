import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api } from '../../api/client';
import type {
  AdminUser,
  Department,
  PasswordResetOut,
  Role,
  UserCreatePayload,
} from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { ErrorMessage, PageHeader, StatusBadge, SuccessMessage } from '../../components/ui';

interface FormState {
  username: string;
  email: string;
  full_name: string;
  password: string;
  roles: string[];
  department_ids: string[];
}

const emptyForm: FormState = {
  username: '',
  email: '',
  full_name: '',
  password: '',
  roles: [],
  department_ids: [],
};

function messageOf(cause: unknown, fallback: string): string {
  return cause instanceof Error ? cause.message : fallback;
}

function toggle(value: string, values: string[]): string[] {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function Users() {
  const { user: currentUser, refresh } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [secret, setSecret] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [loadedUsers, loadedRoles, loadedDepartments] = await Promise.all([
        api.users(),
        api.roles(),
        api.adminDepartments(),
      ]);
      setUsers(loadedUsers);
      setRoles(loadedRoles);
      setDepartments(loadedDepartments);
    } catch (cause) {
      setError(messageOf(cause, 'No fue posible cargar los usuarios.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function startNew() {
    setForm(emptyForm);
    setEditingId(null);
    setError(null);
    setSuccess(null);
    setSecret(null);
  }

  function startEdit(user: AdminUser) {
    setForm({
      username: user.username,
      email: user.email,
      full_name: user.full_name,
      password: '',
      roles: [...user.roles],
      department_ids: [...user.department_ids],
    });
    setEditingId(user.id);
    setError(null);
    setSuccess(null);
    setSecret(null);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    setSecret(null);
    if (!form.username.trim() || !form.email.trim() || !form.full_name.trim()) {
      setError('Usuario, correo y nombre completo son obligatorios.');
      return;
    }
    setSaving(true);
    try {
      if (editingId) {
        await api.updateUser(editingId, {
          email: form.email.trim(),
          full_name: form.full_name.trim(),
          department_ids: form.department_ids,
        });
        setSuccess('Usuario actualizado correctamente.');
      } else {
        const payload: UserCreatePayload = {
          username: form.username.trim(),
          email: form.email.trim(),
          full_name: form.full_name.trim(),
          roles: form.roles,
          department_ids: form.department_ids,
        };
        if (form.password) payload.password = form.password;
        const created = await api.createUser(payload);
        if (created.temporary_password) {
          setSecret(
            `Contraseña temporal de ${created.username}: ${created.temporary_password}. Cópiela ahora; no se volverá a mostrar.`,
          );
        } else {
          setSuccess(`Usuario ${created.username} creado correctamente.`);
        }
      }
      setForm(emptyForm);
      setEditingId(null);
      await load();
    } catch (cause) {
      setError(messageOf(cause, 'No fue posible guardar el usuario.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleRole(user: AdminUser, roleCode: string) {
    setError(null);
    setSuccess(null);
    try {
      if (user.roles.includes(roleCode)) {
        await api.removeRole(user.id, roleCode);
      } else {
        await api.assignRole(user.id, roleCode);
      }
      setSuccess(`Roles de ${user.username} actualizados.`);
      await load();
      if (user.id === currentUser?.id) await refresh();
    } catch (cause) {
      setError(messageOf(cause, 'No fue posible modificar los roles.'));
    }
  }

  async function handleToggleStatus(user: AdminUser) {
    setError(null);
    setSuccess(null);
    try {
      const nextStatus = user.status === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
      await api.updateUser(user.id, { status: nextStatus });
      setSuccess(`Estado de ${user.username} actualizado a ${nextStatus}.`);
      await load();
    } catch (cause) {
      setError(messageOf(cause, 'No fue posible cambiar el estado.'));
    }
  }

  async function handleReset(user: AdminUser) {
    setError(null);
    setSuccess(null);
    setSecret(null);
    try {
      const result: PasswordResetOut = await api.resetPassword(
        user.id,
        'Restablecimiento solicitado desde el panel de usuarios',
      );
      setSecret(
        `Contraseña temporal de ${result.username}: ${result.temporary_password}. Debe cambiarse en el primer acceso.`,
      );
      await load();
    } catch (cause) {
      setError(messageOf(cause, 'No fue posible restablecer la contraseña.'));
    }
  }

  async function handleDeactivate(user: AdminUser) {
    if (!window.confirm(`¿Dar de baja a ${user.username}? La baja es lógica y quedará en la bitácora.`)) {
      return;
    }
    setError(null);
    try {
      await api.deactivateUser(user.id);
      setSuccess(`Usuario ${user.username} dado de baja lógicamente.`);
      await load();
    } catch (cause) {
      setError(messageOf(cause, 'No fue posible dar de baja al usuario.'));
    }
  }

  return (
    <>
      <PageHeader
        title="Administración de usuarios"
        subtitle="Altas, bajas lógicas, roles, departamentos y restablecimiento seguro de contraseñas"
      />
      <ErrorMessage message={error} />
      <SuccessMessage message={success} />
      {secret && (
        <div className="alert alert-warning secret-box" role="status">
          <strong>Contraseña temporal (única vez):</strong> {secret}
        </div>
      )}

      <section className="panel">
        <h2>{editingId ? 'Editar usuario' : 'Nuevo usuario'}</h2>
        <form onSubmit={handleSubmit}>
          <div className="grid-3">
            <label>
              Usuario
              <input
                value={form.username}
                onChange={(event) => setForm({ ...form, username: event.target.value })}
                disabled={Boolean(editingId)}
                required
              />
            </label>
            <label>
              Correo
              <input
                type="email"
                value={form.email}
                onChange={(event) => setForm({ ...form, email: event.target.value })}
                required
              />
            </label>
            <label>
              Nombre completo
              <input
                value={form.full_name}
                onChange={(event) => setForm({ ...form, full_name: event.target.value })}
                required
              />
            </label>
          </div>
          {!editingId && (
            <label>
              Contraseña (vacío para generar una temporal)
              <input
                type="password"
                value={form.password}
                onChange={(event) => setForm({ ...form, password: event.target.value })}
                autoComplete="new-password"
              />
            </label>
          )}

          <h3>Roles</h3>
          <div className="option-grid">
            {roles.map((role) => (
              <label className="checkbox-line" key={role.code}>
                <input
                  type="checkbox"
                  checked={form.roles.includes(role.code)}
                  onChange={() => setForm({ ...form, roles: toggle(role.code, form.roles) })}
                  disabled={role.code === 'ADMIN' && editingId === currentUser?.id}
                />
                {role.name}
              </label>
            ))}
          </div>

          <h3>Departamentos asignados</h3>
          <div className="option-grid">
            {departments.map((department) => (
              <label className="checkbox-line" key={department.id}>
                <input
                  type="checkbox"
                  checked={form.department_ids.includes(department.id)}
                  onChange={() =>
                    setForm({
                      ...form,
                      department_ids: toggle(department.id, form.department_ids),
                    })
                  }
                />
                {department.code} — {department.name ?? ''}
              </label>
            ))}
          </div>

          <div className="form-actions">
            <button className="button button-primary" type="submit" disabled={saving}>
              {saving ? 'Guardando…' : editingId ? 'Guardar cambios' : 'Crear usuario'}
            </button>
            {(editingId || form.username || form.email) && (
              <button className="button button-ghost" type="button" onClick={startNew}>
                Cancelar
              </button>
            )}
          </div>
        </form>
      </section>

      <section className="panel">
        <h2>Usuarios registrados</h2>
        {loading ? (
          <p className="empty">Cargando usuarios…</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Usuario</th>
                  <th>Nombre</th>
                  <th>Estado</th>
                  <th>Roles</th>
                  <th>Departamentos</th>
                  <th>Intentos fallidos</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <strong>{user.username}</strong>
                      <br />
                      <small>{user.email}</small>
                    </td>
                    <td>{user.full_name}</td>
                    <td>
                      <StatusBadge status={user.status} />
                      {user.must_change_password && <small className="flag">Contraseña temporal</small>}
                    </td>
                    <td>
                      <div className="role-chips">
                        {user.roles.map((role) => (
                          <button
                            key={role}
                            type="button"
                            className="chip chip-active"
                            title="Quitar rol"
                            disabled={role === 'ADMIN' && user.id === currentUser?.id}
                            onClick={() => void handleToggleRole(user, role)}
                          >
                            {role} ×
                          </button>
                        ))}
                        {roles
                          .filter((role) => !user.roles.includes(role.code))
                          .map((role) => (
                            <button
                              key={role.code}
                              type="button"
                              className="chip"
                              title="Asignar rol"
                              onClick={() => void handleToggleRole(user, role.code)}
                            >
                              + {role.code}
                            </button>
                          ))}
                      </div>
                    </td>
                    <td>{user.department_ids.length}</td>
                    <td>{user.failed_login_attempts}</td>
                    <td>
                      <div className="actions">
                        <button className="button button-small" type="button" onClick={() => startEdit(user)}>
                          Editar
                        </button>
                        <button className="button button-small" type="button" onClick={() => void handleReset(user)}>
                          Restablecer
                        </button>
                        <button
                          className="button button-small"
                          type="button"
                          onClick={() => void handleToggleStatus(user)}
                          disabled={user.id === currentUser?.id}
                        >
                          {user.status === 'ACTIVE' ? 'Inactivar' : 'Activar'}
                        </button>
                        <button
                          className="button button-small button-danger"
                          type="button"
                          onClick={() => void handleDeactivate(user)}
                          disabled={user.id === currentUser?.id}
                        >
                          Dar de baja
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
