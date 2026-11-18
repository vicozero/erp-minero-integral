import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

const links = [
  { to: '/', label: 'Dashboard', icon: '▦' },
  { to: '/requisiciones', label: 'Requisiciones', icon: '▤' },
  { to: '/autorizaciones', label: 'Autorizaciones', icon: '✓' },
  { to: '/almacen', label: 'Almacén', icon: '▣' },
  { to: '/compras', label: 'Compras', icon: '▧' },
  { to: '/historial', label: 'Historial', icon: '◷' },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

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
          {links.map((link) => (
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
            <small>{user?.roles.join(', ') ?? ''}</small>
          </div>
          <button
            type="button"
            className="button button-ghost"
            onClick={() => {
              logout();
              navigate('/login');
            }}
          >
            Cerrar sesión
          </button>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
