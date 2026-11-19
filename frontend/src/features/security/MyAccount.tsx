import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, describeApiError } from '../../api/client';
import type { Session } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import {
  EmptyState,
  ErrorMessage,
  LoadingState,
  PageHeader,
  Panel,
  SuccessMessage,
} from '../../components/ui';
import { PasswordChangeForm } from '../auth/ChangePassword';

function formatDate(value: string | null): string {
  if (!value) return '—';
  return new Intl.DateTimeFormat('es-MX', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(value));
}

export function MyAccount() {
  const { user, changeUsername } = useAuth();
  const [username, setUsername] = useState(user?.username ?? '');
  const [currentPassword, setCurrentPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [sessionError, setSessionError] = useState<string | null>(null);

  const loadSessions = useCallback(async () => {
    setLoadingSessions(true);
    setSessionError(null);
    try {
      setSessions(await api.mySessions());
    } catch (cause) {
      setSessionError(describeApiError(cause, 'No fue posible consultar las sesiones activas.'));
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (user) setUsername(user.username);
  }, [user?.username]);

  async function handleUsername(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    if (username.trim() === user?.username) {
      setError('El nombre de usuario no ha cambiado.');
      return;
    }
    setSaving(true);
    try {
      await changeUsername(username.trim(), currentPassword);
      setSuccess('Nombre de usuario actualizado. Las otras sesiones fueron cerradas.');
      setCurrentPassword('');
      await loadSessions();
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible actualizar el nombre de usuario.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleRevoke(session: Session) {
    setSessionError(null);
    try {
      await api.revokeSession(session.id);
      await loadSessions();
    } catch (cause) {
      setSessionError(describeApiError(cause, 'No fue posible revocar la sesión.'));
    }
  }

  return (
    <>
      <PageHeader
        title="Mi cuenta"
        subtitle="Administración · Seguridad · Cambio de credenciales y sesiones propias"
      />

      <div className="panel-grid">
        <Panel title="Identificación" subtitle="El cambio requiere la contraseña actual y cierra otras sesiones.">
          <ErrorMessage message={error} />
          <SuccessMessage message={success} />
          <form onSubmit={handleUsername}>
            <label htmlFor="account-username">Nombre de usuario</label>
            <input
              id="account-username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              pattern="[A-Za-z0-9._-]{3,80}"
              minLength={3}
              maxLength={80}
              required
            />
            <label htmlFor="account-current-password">Contraseña actual para cambiar usuario</label>
            <input
              id="account-current-password"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(event) => setCurrentPassword(event.target.value)}
              required
            />
            <p className="hint">Solo letras, números, punto, guion y guion bajo; de 3 a 80 caracteres.</p>
            <div className="form-actions">
              <button className="button button-primary" type="submit" disabled={saving}>
                {saving ? 'Guardando…' : 'Actualizar usuario'}
              </button>
            </div>
          </form>
          <div className="detail-grid">
            <div><span>Nombre completo</span><strong>{user?.full_name ?? '—'}</strong></div>
            <div><span>Correo</span><strong>{user?.email ?? '—'}</strong></div>
            <div><span>Roles</span><strong>{user?.roles.join(', ') || 'Sin roles'}</strong></div>
            <div><span>Permisos activos</span><strong>{user?.permissions.length ?? 0}</strong></div>
          </div>
        </Panel>

        <Panel
          title="Contraseña"
          subtitle="Política robusta, confirmación y revocación de todas las sesiones anteriores."
        >
          <PasswordChangeForm onChanged={() => void loadSessions()} />
        </Panel>
      </div>

      <Panel title="Sesiones activas" subtitle="Solo se muestran las sesiones de esta cuenta.">
        <ErrorMessage message={sessionError} />
        {loadingSessions ? (
          <LoadingState label="Consultando sesiones…" />
        ) : sessions.length === 0 ? (
          <EmptyState text="No hay sesiones activas." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Creación</th>
                  <th>Última actividad</th>
                  <th>Expira</th>
                  <th>Acción</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.id}>
                    <td>{formatDate(session.created_at)}</td>
                    <td>{formatDate(session.last_seen_at)}</td>
                    <td>{formatDate(session.expires_at)}</td>
                    <td>
                      <button
                        type="button"
                        className="button button-ghost"
                        onClick={() => void handleRevoke(session)}
                      >
                        Revocar
                      </button>
                    </td>
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
