import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { AuditEntry, HistoryEvent, Requisition } from '../../api/types';
import { EmptyState, ErrorMessage, PageHeader, Panel } from '../../components/ui';

export function History() {
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [selected, setSelected] = useState('');
  const [events, setEvents] = useState<HistoryEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.audit(), api.requisitions()])
      .then(([auditData, reqData]) => {
        setAudit(auditData);
        setRequisitions(reqData);
        setSelected(reqData[0]?.id ?? '');
        if (reqData[0]) {
          api.history(reqData[0].id).then(setEvents).catch(() => setEvents([]));
        }
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Error al cargar.'));
  }, []);

  async function loadHistory(id: string) {
    setSelected(id);
    setError(null);
    try {
      setEvents(await api.history(id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible cargar el historial.');
    }
  }

  return (
    <>
      <PageHeader title="Historial y seguimiento" subtitle="Bitácora de auditoría y eventos documentales" />
      <ErrorMessage message={error} />
      <Panel title="Eventos de requisición">
        {requisitions.length === 0 ? (
          <EmptyState text="No hay requisiciones para mostrar." />
        ) : (
          <>
            <label>Requisición
              <select value={selected} onChange={(event) => loadHistory(event.target.value)}>
                {requisitions.map((req) => (
                  <option key={req.id} value={req.id}>{req.document_no}</option>
                ))}
              </select>
            </label>
            {events.length === 0 ? (
              <EmptyState text="Sin eventos." />
            ) : (
              <ol className="timeline">
                {events.map((event, index) => (
                  <li key={index}>
                    <strong>{event.event_type.replaceAll('_', ' ')}</strong>
                    <span>{event.from_status ?? '—'} → {event.to_status ?? '—'}</span>
                    <small>{new Date(event.occurred_at).toLocaleString('es-MX')}</small>
                  </li>
                ))}
              </ol>
            )}
          </>
        )}
      </Panel>

      <Panel title="Bitácora de auditoría">
        {audit.length === 0 ? (
          <EmptyState text="No hay entradas de auditoría." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Fecha</th><th>Actor</th><th>Acción</th><th>Entidad</th><th>Detalle</th></tr></thead>
              <tbody>
                {audit.map((entry) => (
                  <tr key={entry.id}>
                    <td>{new Date(entry.occurred_at).toLocaleString('es-MX')}</td>
                    <td>{entry.actor_username ?? 'sistema'}</td>
                    <td>{entry.action}</td>
                    <td>{entry.entity_type}</td>
                    <td>{entry.detail ?? '—'}</td>
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
