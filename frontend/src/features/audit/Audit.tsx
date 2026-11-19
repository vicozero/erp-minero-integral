import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api } from '../../api/client';
import type { AuditEntry } from '../../api/types';
import { EmptyState, ErrorMessage, PageHeader } from '../../components/ui';

export function Audit() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [action, setAction] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (filter: string) => {
    setLoading(true);
    setError(null);
    try {
      setEntries(await api.audit(200, filter.trim() || undefined));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible consultar la bitácora.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load('');
  }, [load]);

  function handleFilter(event: FormEvent) {
    event.preventDefault();
    void load(action);
  }

  return (
    <>
      <PageHeader
        title="Bitácora de auditoría"
        subtitle="Solo lectura: la aplicación no permite modificar ni eliminar estos registros"
      />
      <ErrorMessage message={error} />
      <section className="panel">
        <form className="filter-bar" onSubmit={handleFilter}>
          <label htmlFor="audit-action">Acción</label>
          <input
            id="audit-action"
            value={action}
            placeholder="Ej. USER_CREATED"
            onChange={(event) => setAction(event.target.value)}
          />
          <button className="button button-primary" type="submit" disabled={loading}>
            Filtrar
          </button>
          <button className="button button-ghost" type="button" onClick={() => {
            setAction('');
            void load('');
          }}>
            Limpiar
          </button>
        </form>
        {entries.length === 0 ? (
          <EmptyState text={loading ? 'Cargando bitácora…' : 'No hay entradas para mostrar.'} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Actor</th>
                  <th>Acción</th>
                  <th>Entidad</th>
                  <th>Detalle</th>
                  <th>Solicitud</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id}>
                    <td>{new Date(entry.occurred_at).toLocaleString('es-MX')}</td>
                    <td>{entry.actor_username ?? 'Sistema'}</td>
                    <td><span className="badge">{entry.action}</span></td>
                    <td>{entry.entity_type}</td>
                    <td>{entry.detail ?? '—'}</td>
                    <td><code>{entry.request_id.slice(0, 12)}</code></td>
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
