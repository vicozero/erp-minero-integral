import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { ErrorMessage } from '../../components/ui';

const demoUsers = [
  'demo.admin',
  'demo.solicitante',
  'demo.jefe',
  'demo.aprobador',
  'demo.almacenista',
  'demo.comprador',
  'demo.gerencia',
  'demo.auditor',
  'demo.temporal',
];

export function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('demo.solicitante');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username.trim(), password);
      navigate('/', { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible iniciar sesión.');
    } finally {
      setLoading(false);
    }
  }

  const needsChange = error?.includes('contraseña temporal');

  return (
    <div className="login-page">
      <section className="login-intro">
        <div className="login-intro-inner">
          <span className="login-emblem">EM</span>
          <h1>ERP MINERO INTEGRAL</h1>
          <p>Control operativo de requisiciones, almacén y compras para la unidad La Guitarra.</p>
          <ul>
            <li>Trazabilidad por documento y usuario</li>
            <li>Acceso por roles y departamentos</li>
            <li>Bitácora inmutable de acciones sensibles</li>
          </ul>
          <small>Ambiente local · datos sintéticos · CONTPAQi sigue siendo el inventario oficial</small>
        </div>
      </section>

      <section className="login-panel">
        <form className="login-card" onSubmit={handleSubmit}>
          <div className="login-heading">
            <span className="brand-mark">EM</span>
            <div>
              <h2>Acceso al sistema</h2>
              <p>Inicie sesión para continuar</p>
            </div>
          </div>

          <label htmlFor="username">Usuario</label>
          <input
            id="username"
            name="username"
            list="demo-users"
            autoComplete="username"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
          />
          <datalist id="demo-users">
            {demoUsers.map((demoUser) => (
              <option key={demoUser} value={demoUser} />
            ))}
          </datalist>

          <label htmlFor="password">Contraseña</label>
          <input
            id="password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          <label className="checkbox-line" htmlFor="show-password">
            <input
              id="show-password"
              type="checkbox"
              checked={showPassword}
              onChange={(event) => setShowPassword(event.target.checked)}
            />
            Mostrar contraseña
          </label>

          <ErrorMessage message={error} />
          {needsChange && (
            <p className="hint">Su cuenta requiere una contraseña nueva; el servidor le solicitará el cambio.</p>
          )}

          <button className="button button-primary login-submit" type="submit" disabled={loading}>
            {loading ? 'Ingresando…' : 'Ingresar'}
          </button>
          <p className="hint">
            Cuentas ficticias de demostración. La contraseña se define en <code>DEMO_PASSWORD</code> del
            archivo <code>.env</code>.
          </p>
        </form>
      </section>
    </div>
  );
}
