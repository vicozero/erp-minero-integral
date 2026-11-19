import { useEffect, useState } from 'react';
import { api, describeApiError } from '../../api/client';
import type { AuditEntry, HistoryEvent, Requisition } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { can, PERM } from '../../auth/permissions';
import { EmptyState, ErrorMessage, LoadingState, PageHeader, Panel, StatusBadge } from '../../components/ui';

const ACTION_OPTIONS = ['', 'CREATE', 'UPDATE', 'SUBMIT', 'APPROVE', 'REJECT', 'CANCEL', 'ISSUE'];

function shortId(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : 'sistema';
}

export function History() {
  const { user } = useAuth();
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [selected, setSelected] = useState('');
  const [events, setEvents] = useState<HistoryEvent[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [action, setAction] = useState('');
  const [limit, setLimit] = useState(100);
  const [auditLoaded, setAuditLoaded] = useState(false);

  const showAudit = can(user, ...PERM.VIEW_AUDIT);

  useEffect(() => {
    let active = true;
    const tasks: Array<Promise<void>> = [
      api.requisitions().then((data) => {
        if (!active) return;
        setRequisitions(data);
        setSelected(data[0]?.id ?? '');
      }),
    ];
    if (showAudit) {
      tasks.push(api.audit().then((data) => {
        if (active) {
          setAudit(data);
          setAuditLoaded(true);
        }
      }));
    }
    Promise.allSettled(tasks).then((results) => {
      if (!active) return;
      const failed = results.find((result) => result.status === 'rejected');
      if (failed && failed.status === 'rejected') {
        setError(describeApiError(failed.reason, 'No fue posible cargar la trazabilidad.'));
      }
      setLoading(false);
    });
    return () => { active = false; };
  }, [showAudit]);

  useEffect(() => {
    let active = true;
    if (!selected) {
      setEvents([]);
      return;
    }
    setEventsLoading(true);
    api.history(selected)
      .then((data) => { if (active) setEvents(data); })
      .catch((cause: unknown) => {
        if (active) setError(describeApiError(cause, 'No fue posible cargar el historial.'));
      })
      .finally(() => { if (active) setEventsLoading(false); });
    return () => { active = false; };
  }, [selected]);

  async function loadAudit(): Promise<void> {
    setError(null);
    try {
      setAudit(await api.audit(limit, action || undefined));
      setAuditLoaded(true);
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible consultar la bitácora.'));
    }
  }

  const selectedReq = requisitions.find((req) => req.id === selected) ?? null;

  return (
    <>
      <PageHeader
        title="Historial y seguimiento"
        subtitle="Eventos documentales de requisiciones y bitácora de auditoría de solo lectura"
      />
      <ErrorMessage message={error} />

      {loading ? (
        <Panel title="Cargando trazabilidad" icon="history">
          <LoadingState rows={5} />
        </Panel>
      ) : (
        <>
          <Panel title="Eventos de requisición" subtitle="La línea de tiempo muestra actor y transición de estado" icon="history">
            {requisitions.length === 0 ? (
              <EmptyState text="No hay requisiciones para mostrar." />
            ) : (
              <>
                <label>
                  Requisición
                  <select value={selected} onChange={(event) => setSelected(event.target.value)}>
                    {requisitions.map((req) => (
                      <option key={req.id} value={req.id}>{req.document_no}</option>
                    ))}
                  </select>
                </label>
                {selectedReq && (
                  <div className="chip-row">
                    <StatusBadge status={selectedReq.status} />
                    <span className="chip">{selectedReq.lines.length} partida(s)</span>
                    <span className="chip">{selectedReq.requisition_type}</span>
                  </div>
                )}
                {eventsLoading ? (
                  <LoadingState rows={3} label="Cargando eventos…" />
                ) : events.length === 0 ? (
                  <EmptyState text="Sin eventos registrados para esta requisición." />
                ) : (
                  <ol className="timeline">
                    {events.map((event, index) => (
                      <li key={index}>
                        <strong>{event.event_type.replaceAll('_', ' ')}</strong>
                        <span>{event.from_status ?? '—'} → {event.to_status ?? '—'}</span>
                        <small>
                          {new Date(event.occurred_at).toLocaleString('es-MX')} · Actor {shortId(event.actor_id)}
                          {event.metadata ? ` · ${JSON.stringify(event.metadata).slice(0, 160)}` : ''}
                        </small>
                      </li>
                    ))}
                  </ol>
                )}
              </>
            )}
          </Panel>

          {showAudit ? (
            <Panel title="Bitácora de auditoría" subtitle="Registro inmutable; no se puede editar desde la aplicación" icon="audit">
              <div className="grid-3">
                <label>
                  Acción
                  <select value={action} onChange={(event) => setAction(event.target.value)}>
                    {ACTION_OPTIONS.map((value) => (
                      <option key={value} value={value}>{value || 'Todas'}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Límite
                  <select value={limit} onChange={(event) => setLimit(Number(event.target.value))}>
                    {[50, 100, 200, 500].map((value) => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                </label>
                <div className="align-end">
                  <button className="button button-secondary" type="button" onClick={() => void loadAudit()}>
                    Aplicar filtros
                  </button>
                </div>
              </div>
              {!auditLoaded ? (
                <LoadingState rows={3} label="Cargando bitácora…" />
              ) : audit.length === 0 ? (
                <EmptyState text="No hay entradas de auditoría para el alcance del usuario." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr><th>Fecha</th><th>Actor</th><th>Acción</th><th>Entidad</th><th>Detalle</th><th>Solicitud</th></tr>
                    </thead>
                    <tbody>
                      {audit.map((entry) => (
                        <tr key={entry.id}>
                          <td>{new Date(entry.occurred_at).toLocaleString('es-MX')}</td>
                          <td>{entry.actor_username ?? 'sistema'}</td>
                          <td>{entry.action}</td>
                          <td>{entry.entity_type} · {shortId(entry.entity_id)}</td>
                          <td>{entry.detail ?? '—'}</td>
                          <td><small>{shortId(entry.request_id)}</small></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>
          ) : (
            <Panel title="Bitácora de auditoría" subtitle="No disponible para el rol activo" icon="audit">
              <EmptyState text="Su perfil no cuenta con el permiso auditoria.consultar. El historial documental sí está disponible." />
            </Panel>
          )}
        </>
      )}
    </>
  );
}
