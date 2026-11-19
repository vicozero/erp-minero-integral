import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { can, PERM } from '../auth/permissions';

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

const links = [
  { to: '/', label: 'Dashboard', icon: '▦', codes: [] as string[] },
  { to: '/requisiciones', label: 'Requisiciones', icon: '▤', codes: PERM.VIEW_REQUISITIONS },
  { to: '/autorizaciones', label: 'Autorizaciones', icon: '✓', codes: PERM.APPROVE_REQUISITIONS },
  { to: '/almacen', label: 'Almacén', icon: '▣', codes: PERM.VIEW_INVENTORY },
  { to: '/compras', label: 'Compras', icon: '▧', codes: PERM.VIEW_PURCHASES },
  { to: '/historial', label: 'Historial', icon: '◷', codes: PERM.VIEW_HISTORY },
  { to: '/usuarios', label: 'Usuarios', icon: '☰', codes: PERM.ADMIN_USERS },
  { to: '/auditoria', label: 'Auditoría', icon: '▥', codes: PERM.VIEW_AUDIT },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const visibleLinks = links.filter(
    (link) => link.codes.length === 0 || can(user, ...link.codes),
  );
  const roles = (user?.roles ?? []).map((role) => roleLabels[role] ?? role.replaceAll('_', ' '));

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
            <small>INTEGRAL · Local</small>
          </div>
        </div>
        <nav aria-label="Menú principal">
          {visibleLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) => (isActive ? 'nav-link active' : 'nav-link')}
            >
              <span aria-hidden="true">{link.icon}</span>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <small>Inventario operativo</small>
          <small>CONTPAQi: sistema oficial</small>
        </div>
      </aside>
      <div className="main-area">
        <header className="topbar">
          <div>
            <strong>{user?.full_name ?? 'Usuario'}</strong>
            <small>{roles.join(' · ') || 'Sin roles asignados'}</small>
          </div>
          <div className="topbar-actions">
            <NavLink className="button button-ghost" to="/cambiar-contraseña">
              Cambiar contraseña
            </NavLink>
            <button type="button" className="button button-ghost" onClick={handleLogout}>
              Cerrar sesión
            </button>
          </div>
        </header>
        <main className="content">
          {user?.must_change_password && (
            <div className="alert alert-warning" role="status">
              Su contraseña es temporal. Debe cambiarla antes de continuar.{' '}
              <NavLink to="/cambiar-contraseña">Cambiar ahora</NavLink>
            </div>
          )}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
