import { useState, type FormEvent } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { ErrorMessage } from '../../components/ui';

const demoUsers = [
  'demo.admin',
  'demo.solicitante',
  'demo.aprobador',
  'demo.almacenista',
  'demo.comprador',
];

export function Login() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('demo.solicitante');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible iniciar sesión.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={handleSubmit}>
        <div className="login-brand">
          <span className="brand-mark">EM</span>
          <div>
            <h1>ERP MINERO INTEGRAL</h1>
            <p>Acceso local · datos ficticios</p>
          </div>
        </div>
        <label htmlFor="username">Usuario</label>
        <select
          id="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        >
          {demoUsers.map((demoUser) => (
            <option key={demoUser} value={demoUser}>{demoUser}</option>
          ))}
        </select>
        <label htmlFor="password">Contraseña</label>
        <input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          required
        />
        <ErrorMessage message={error} />
        <button className="button button-primary" type="submit" disabled={loading}>
          {loading ? 'Ingresando…' : 'Ingresar'}
        </button>
        <p className="hint">
          La contraseña se define en <code>DEMO_PASSWORD</code> del archivo <code>.env</code>.
        </p>
      </form>
    </div>
  );
}
