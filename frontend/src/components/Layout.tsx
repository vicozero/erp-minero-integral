import { useMemo, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { can, PERM } from '../auth/permissions';
import { Icon, type IconName } from './Icon';

const roleLabels: Record<string, string> = {
  ADMIN: 'Administrador',
  SOLICITANTE: 'Solicitante',
  JEFE_DEPARTAMENTO: 'Jefe de departamento',
  APROBADOR: 'Aprobador',
  ALMACENISTA: 'Almacén',
  ALMACEN: 'Almacén',
  COMPRADOR: 'Compras',
  COMPRAS: 'Compras',
  GERENCIA: 'Gerencia',
  AUDITOR: 'Auditor',
};

type NavItem = { to: string; label: string; icon: IconName; codes: readonly string[] };

const navGroups: { label: string; items: NavItem[] }[] = [
  {
    label: 'Operación',
    items: [
      { to: '/', label: 'Dashboard', icon: 'dashboard', codes: [] },
      { to: '/requisiciones', label: 'Requisiciones', icon: 'requisitions', codes: PERM.VIEW_REQUISITIONS },
      { to: '/autorizaciones', label: 'Autorizaciones', icon: 'approve', codes: PERM.APPROVE_REQUISITIONS },
      { to: '/almacen', label: 'Almacén', icon: 'warehouse', codes: PERM.VIEW_INVENTORY },
      { to: '/compras', label: 'Compras', icon: 'purchases', codes: PERM.VIEW_PURCHASES },
    ],
  },
  {
    label: 'Trazabilidad',
    items: [
      { to: '/historial', label: 'Historial', icon: 'history', codes: PERM.VIEW_HISTORY },
      { to: '/auditoria', label: 'Auditoría', icon: 'audit', codes: PERM.VIEW_AUDIT },
    ],
  },
  {
    label: 'Administración',
    items: [
      { to: '/usuarios', label: 'Usuarios', icon: 'users', codes: PERM.ADMIN_USERS },
    ],
  },
];

function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const [dark, setDark] = useState(() => document.documentElement.dataset.theme === 'dark');

  const groups = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return navGroups
      .map((group) => ({
        ...group,
        items: group.items.filter(
          (item) =>
            (item.codes.length === 0 || can(user, ...item.codes)) &&
            (needle === '' || item.label.toLowerCase().includes(needle)),
        ),
      }))
      .filter((group) => group.items.length > 0);
  }, [user, query]);

  const roles = (user?.roles ?? []).map((role) => roleLabels[role] ?? role.replaceAll('_', ' '));

  function toggleTheme() {
    const next = !dark;
    setDark(next);
    document.documentElement.dataset.theme = next ? 'dark' : 'light';
  }

  async function handleLogout() {
    await logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">EM</span>
          <div>
            <strong>ERP MINERO</strong>
            <small>INTEGRAL · LOCAL</small>
          </div>
        </div>
        <nav aria-label="Menú principal">
          {groups.map((group) => (
            <div className="nav-section" key={group.label}>
              <div className="nav-label">{group.label}</div>
              {group.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
                >
                  <Icon name={item.icon} size={17} />
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
          {groups.length === 0 && <div className="nav-label">Sin módulos para “{query}”</div>}
        </nav>
        <div className="sidebar-footer">
          <small>Inventario operativo · espejo del ERP</small>
          <small>CONTPAQi: sistema oficial</small>
        </div>
      </aside>

      <div className="main-area">
        <header className="topbar">
          <div className="topbar-user">
            <span className="avatar">{initials(user?.full_name ?? 'Usuario')}</span>
            <div>
              <strong>{user?.full_name ?? 'Usuario'}</strong>
              <small>
                {roles.join(' · ') || 'Sin roles asignados'} · Unidad: La Guitarra
              </small>
            </div>
          </div>

          <label className="topbar-search">
            <Icon name="search" size={16} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar módulo…"
              aria-label="Buscar módulo del menú"
            />
          </label>

          <div className="topbar-actions">
            <button
              type="button"
              className="icon-button"
              onClick={toggleTheme}
              aria-label={dark ? 'Activar modo claro' : 'Activar modo oscuro'}
              title={dark ? 'Modo claro' : 'Modo oscuro'}
            >
              <Icon name={dark ? 'sun' : 'moon'} size={17} />
            </button>
            <NavLink className="button button-ghost" to="/cambiar-contraseña">
              <Icon name="key" size={14} />
              Cambiar contraseña
            </NavLink>
            <button type="button" className="button button-ghost" onClick={handleLogout}>
              <Icon name="logout" size={14} />
              Cerrar sesión
            </button>
          </div>
        </header>

        <main className="content">
          {user?.must_change_password && (
            <div className="alert alert-warning" role="status">
              <Icon name="key" size={16} />
              <span>
                Su contraseña es temporal. Debe cambiarla antes de continuar.{' '}
                <NavLink to="/cambiar-contraseña">Cambiar ahora</NavLink>
              </span>
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
