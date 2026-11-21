import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { ErrorMessage, PageHeader, SuccessMessage } from '../../components/ui';

const PASSWORD_MIN_LENGTH = 6;

export function PasswordChangeForm({ onChanged }: { onChanged?: () => void }) {
  const { changePassword, user } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (next !== confirm) {
      setError('La confirmación no coincide con la contraseña nueva.');
      return;
    }
    setLoading(true);
    try {
      await changePassword(current, next);
      setSuccess('Contraseña actualizada. Todas las sesiones anteriores fueron cerradas.');
      setCurrent('');
      setNext('');
      setConfirm('');
      onChanged?.();
      if (user?.must_change_password) {
        window.setTimeout(() => navigate('/', { replace: true }), 900);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible cambiar la contraseña.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <ErrorMessage message={error} />
      <SuccessMessage message={success} />
      {user?.must_change_password && (
        <div className="alert alert-warning" role="status">
          Su contraseña temporal debe sustituirse antes de continuar con las operaciones.
        </div>
      )}
      <form onSubmit={handleSubmit}>
        <label htmlFor="current-password">Contraseña actual</label>
        <input
          id="current-password"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(event) => setCurrent(event.target.value)}
          required
        />
        <label htmlFor="new-password">Contraseña nueva</label>
        <input
          id="new-password"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(event) => setNext(event.target.value)}
          minLength={PASSWORD_MIN_LENGTH}
          required
        />
        <label htmlFor="confirm-password">Confirmar contraseña nueva</label>
        <input
          id="confirm-password"
          type="password"
          autoComplete="new-password"
          value={confirm}
          onChange={(event) => setConfirm(event.target.value)}
          minLength={PASSWORD_MIN_LENGTH}
          required
        />
        <p className="hint">
          Mínimo {PASSWORD_MIN_LENGTH} caracteres, con mayúscula, minúscula, número y carácter
          especial.
        </p>
        <div className="form-actions">
          <button className="button button-primary" type="submit" disabled={loading}>
            {loading ? 'Guardando…' : 'Actualizar contraseña'}
          </button>
        </div>
      </form>
    </>
  );
}

export function ChangePassword() {
  return (
    <>
      <PageHeader
        title="Cambiar contraseña"
        subtitle="La contraseña se almacena con Argon2id; nunca se muestra ni se registra"
      />
      <section className="panel panel-narrow">
        <PasswordChangeForm />
      </section>
    </>
  );
}
