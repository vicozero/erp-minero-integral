import { useEffect, useMemo, useState } from 'react';
import { api, describeApiError } from '../../api/client';
import type { Permission, Role } from '../../api/types';
import {
  EmptyState,
  ErrorMessage,
  LoadingState,
  PageHeader,
  Panel,
} from '../../components/ui';

export function Roles() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.roles()
      .then((rows) => { if (active) setRoles(rows); })
      .catch((cause) => { if (active) setError(describeApiError(cause, 'No fue posible consultar los roles.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  return (
    <>
      <PageHeader
        title="Roles"
        subtitle="Administración · Seguridad · Catálogo RBAC. La asignación se realiza desde Usuarios."
      />
      <Panel title="Catálogo de roles">
        <ErrorMessage message={error} />
        {loading ? (
          <LoadingState label="Consultando roles…" />
        ) : roles.length === 0 ? (
          <EmptyState text="No hay roles registrados." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Código</th><th>Nombre</th><th>Descripción</th></tr>
              </thead>
              <tbody>
                {roles.map((role) => (
                  <tr key={role.code}>
                    <td><span className="badge">{role.code}</span></td>
                    <td>{role.name}</td>
                    <td>{role.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

export function Permissions() {
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api.permissions()
      .then((rows) => { if (active) setPermissions(rows); })
      .catch((cause) => { if (active) setError(describeApiError(cause, 'No fue posible consultar los permisos.')); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return permissions;
    return permissions.filter(
      (permission) =>
        permission.code.toLowerCase().includes(needle) ||
        (permission.description ?? '').toLowerCase().includes(needle),
    );
  }, [permissions, query]);

  return (
    <>
      <PageHeader
        title="Permisos"
        subtitle="Administración · Seguridad · Catálogo de permisos disponibles en backend."
      />
      <Panel title={`Permisos registrados (${permissions.length})`}>
        <ErrorMessage message={error} />
        <div className="search-toolbar">
          <label>
            Buscar permiso
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Código o descripción"
            />
          </label>
        </div>
        {loading ? (
          <LoadingState label="Consultando permisos…" />
        ) : filtered.length === 0 ? (
          <EmptyState text="No hay permisos que coincidan con la búsqueda." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Código</th><th>Descripción</th></tr></thead>
              <tbody>
                {filtered.map((permission) => (
                  <tr key={permission.code}>
                    <td><span className="badge">{permission.code}</span></td>
                    <td>{permission.description || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
