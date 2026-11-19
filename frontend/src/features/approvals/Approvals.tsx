import { useEffect, useMemo, useState } from 'react';
import { api, describeApiError } from '../../api/client';
import type { ApprovalDecision, Catalogs, HistoryEvent, Requisition, RequisitionLine } from '../../api/types';
import {
  ConfirmDialog,
  EmptyState,
  ErrorMessage,
  formatNumber,
  InlineFieldError,
  LoadingState,
  PageHeader,
  Panel,
  PriorityBadge,
  StatusBadge,
  SuccessMessage,
} from '../../components/ui';

interface LineChoice {
  selected: boolean;
  quantity: string;
  reason: string;
}

interface ConfirmState {
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
}

type ChoiceMap = Record<string, LineChoice>;
type DecisionMode = 'APPROVE_SELECTED' | 'REJECT_SELECTED' | 'APPROVE_ALL' | 'REJECT_ALL';

const MODE_LABELS: Record<DecisionMode, { title: string; label: string; confirmLabel: string }> = {
  APPROVE_SELECTED: {
    title: 'Confirmar autorización parcial',
    label: 'Autorizar seleccionadas',
    confirmLabel: 'Sí, autorizar seleccionadas',
  },
  APPROVE_ALL: {
    title: 'Confirmar autorización total',
    label: 'Autorizar todo',
    confirmLabel: 'Sí, autorizar todo',
  },
  REJECT_SELECTED: {
    title: 'Confirmar rechazo parcial',
    label: 'Rechazar seleccionadas',
    confirmLabel: 'Sí, rechazar seleccionadas',
  },
  REJECT_ALL: {
    title: 'Confirmar rechazo total',
    label: 'Rechazar todo',
    confirmLabel: 'Sí, rechazar todo',
  },
};

function defaultChoices(lines: RequisitionLine[]): ChoiceMap {
  return Object.fromEntries(
    lines.map((line) => [
      line.id,
      { selected: true, quantity: line.requested_qty, reason: '' } satisfies LineChoice,
    ]),
  );
}

function quantityError(choice: LineChoice, line: RequisitionLine): string | null {
  const qty = Number(choice.quantity);
  if (choice.quantity.trim() === '' || !Number.isFinite(qty)) return 'Indique una cantidad válida.';
  if (qty < 0 || qty > Number(line.requested_qty)) return 'No puede exceder la cantidad solicitada.';
  return null;
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString('es-MX') : '—';
}

export function Approvals() {
  const [pending, setPending] = useState<Requisition[]>([]);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [choices, setChoices] = useState<Record<string, ChoiceMap>>({});
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [priorityFilter, setPriorityFilter] = useState('');
  const [departmentFilter, setDepartmentFilter] = useState('');
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [history, setHistory] = useState<{ id: string; events: HistoryEvent[] } | null>(null);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);

  async function reload(): Promise<void> {
    const all = await api.requisitions();
    const submitted = all.filter((req) => req.status === 'SUBMITTED');
    setPending(submitted);
    setChoices(Object.fromEntries(submitted.map((req) => [req.id, defaultChoices(req.lines)])));
  }

  useEffect(() => {
    let active = true;
    Promise.allSettled([api.requisitions(), api.catalogs()]).then(([reqResult, catResult]) => {
      if (!active) return;
      if (reqResult.status === 'fulfilled') {
        const submitted = reqResult.value.filter((req) => req.status === 'SUBMITTED');
        setPending(submitted);
        setChoices(Object.fromEntries(submitted.map((req) => [req.id, defaultChoices(req.lines)])));
      } else {
        setError(describeApiError(reqResult.reason, 'No fue posible cargar la bandeja.'));
      }
      if (catResult.status === 'fulfilled') setCatalogs(catResult.value);
      setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const visible = useMemo(() => pending.filter((req) => {
    if (priorityFilter && req.priority !== priorityFilter) return false;
    if (departmentFilter && req.department_id !== departmentFilter) return false;
    if (query && !req.document_no.toLowerCase().includes(query.toLowerCase())
      && !req.justification.toLowerCase().includes(query.toLowerCase())) return false;
    return true;
  }), [pending, priorityFilter, departmentFilter, query]);

  const uomLabel = (id: string): string =>
    catalogs?.uoms.find((uom) => uom.id === id)?.code ?? id.slice(0, 8);
  const catalogLabel = (key: 'departments' | 'warehouses' | 'equipment' | 'cost_centers', id: string | null): string => {
    if (!id) return 'No asignado';
    const item = catalogs?.[key].find((candidate) => candidate.id === id);
    return item?.name ?? item?.code ?? id.slice(0, 8);
  };

  function updateChoice(requisitionId: string, lineId: string, patch: Partial<LineChoice>): void {
    setChoices((current) => ({
      ...current,
      [requisitionId]: {
        ...(current[requisitionId] ?? {}),
        [lineId]: {
          ...(current[requisitionId]?.[lineId] ?? { selected: true, quantity: '0', reason: '' }),
          ...patch,
        },
      },
    }));
  }

  function setAll(requisitionId: string, selected: boolean): void {
    const req = pending.find((candidate) => candidate.id === requisitionId);
    if (!req) return;
    setChoices((current) => ({
      ...current,
      [requisitionId]: Object.fromEntries(
        req.lines.map((line) => [line.id, {
          selected,
          quantity: current[requisitionId]?.[line.id]?.quantity ?? line.requested_qty,
          reason: current[requisitionId]?.[line.id]?.reason ?? '',
        } satisfies LineChoice]),
      ),
    }));
  }

  function buildDecisions(req: Requisition, mode: DecisionMode): ApprovalDecision[] {
    const current = choices[req.id] ?? defaultChoices(req.lines);
    const rejectSelected = mode === 'REJECT_SELECTED';
    const rejectAll = mode === 'REJECT_ALL';
    const approveAll = mode === 'APPROVE_ALL';
    const rejectMode = rejectSelected || rejectAll;

    return req.lines.map((line) => {
      const choice = current[line.id] ?? { selected: true, quantity: line.requested_qty, reason: '' };
      const selected = approveAll || rejectAll || choice.selected;
      if (!selected) {
        // Al rechazar solo algunas partidas, las demás se autorizan completas
        // para que la decisión no cancele líneas que el aprobador no tocó.
        return rejectSelected
          ? {
              requisition_line_id: line.id,
              decision: 'APPROVE' as const,
              approved_qty: line.requested_qty,
            }
          : {
              requisition_line_id: line.id,
              decision: 'APPROVE' as const,
              approved_qty: '0',
              reason: choice.reason || reason || 'Partida no autorizada en esta decisión.',
            };
      }
      if (rejectMode) {
        return {
          requisition_line_id: line.id,
          decision: 'REJECT' as const,
          approved_qty: '0',
          reason: choice.reason || reason,
        };
      }
      return {
        requisition_line_id: line.id,
        decision: 'APPROVE' as const,
        approved_qty: approveAll ? line.requested_qty : choice.quantity || line.requested_qty,
      };
    });
  }

  function requestDecide(req: Requisition, mode: DecisionMode): void {
    if (busyId) return;
    setError(null);
    setNotice(null);
    const current = choices[req.id] ?? defaultChoices(req.lines);
    const rejectMode = mode === 'REJECT_SELECTED' || mode === 'REJECT_ALL';
    const invalid = req.lines.find((line) => {
      const choice = current[line.id];
      if (!choice || !choice.selected || rejectMode) return false;
      return quantityError(choice, line) !== null;
    });
    if (invalid) {
      setError(`Revise la cantidad autorizada de la partida ${invalid.line_no}.`);
      return;
    }
    const decisions = buildDecisions(req, mode);
    if (decisions.some((item) => item.decision === 'REJECT' && !item.reason)) {
      setError('Indique un motivo general o un motivo por partida para los rechazos.');
      return;
    }
    const meta = MODE_LABELS[mode];
    setConfirm({
      title: meta.title,
      message: `${req.document_no}: se enviarán ${decisions.length} decisiones al servidor. El backend validará permisos y estado.`,
      confirmLabel: meta.confirmLabel,
      onConfirm: () => void executeDecide(req, decisions),
    });
  }

  async function executeDecide(req: Requisition, decisions: ApprovalDecision[]): Promise<void> {
    if (busyId) return;
    setBusyId(req.id);
    try {
      const result = await api.decideRequisition(req.id, decisions, reason || undefined);
      setNotice(`${req.document_no}: ${result.status.replaceAll('_', ' ')}.`);
      setReason('');
      setHistory(null);
      await reload();
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible registrar la decisión.'));
    } finally {
      setBusyId(null);
    }
  }

  async function handleHistory(req: Requisition): Promise<void> {
    setError(null);
    try {
      setHistory({ id: req.id, events: await api.history(req.id) });
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible cargar el historial de autorizaciones.'));
    }
  }

  const counts = {
    urgent: pending.filter((req) => req.priority === 'URGENT').length,
    high: pending.filter((req) => req.priority === 'HIGH').length,
    lines: pending.reduce((total, req) => total + req.lines.length, 0),
  };

  return (
    <>
      <PageHeader
        title="Autorizaciones"
        subtitle="Bandeja de requisiciones enviadas · decisión por partida con confirmación"
      />
      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />

      {loading ? (
        <Panel title="Cargando bandeja" icon="approve">
          <LoadingState rows={5} />
        </Panel>
      ) : (
        <>
          <div className="card-grid compact">
            <div className="metric-card tone-warning"><span>Pendientes</span><strong>{pending.length}</strong><small>Documentos enviados</small></div>
            <div className="metric-card"><span>Partidas por revisar</span><strong>{counts.lines}</strong><small>Decisión individual</small></div>
            <div className="metric-card tone-info"><span>Prioridad crítica/alta</span><strong>{counts.urgent + counts.high}</strong><small>{counts.urgent} crítica(s)</small></div>
          </div>

          <Panel title="Criterios de bandeja" subtitle="El backend vuelve a validar permisos, rol y estado" icon="search">
            <div className="grid-3">
              <label>
                Buscar folio o justificación
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="REQ-LAG…" />
              </label>
              <label>
                Prioridad
                <select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}>
                  <option value="">Todas</option>
                  <option value="LOW">Baja</option>
                  <option value="NORMAL">Normal</option>
                  <option value="HIGH">Alta</option>
                  <option value="URGENT">Crítica</option>
                </select>
              </label>
              <label>
                Departamento
                <select value={departmentFilter} onChange={(event) => setDepartmentFilter(event.target.value)}>
                  <option value="">Todos</option>
                  {catalogs?.departments.map((item) => (
                    <option key={item.id} value={item.id}>{item.name ?? item.code}</option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Motivo general (obligatorio en rechazos)
              <input value={reason} onChange={(event) => setReason(event.target.value)} />
            </label>
          </Panel>

          {visible.length === 0 ? (
            <EmptyState text="No hay requisiciones pendientes con estos criterios." />
          ) : (
            visible.map((req) => {
              const current = choices[req.id] ?? defaultChoices(req.lines);
              const isOpen = expanded[req.id] !== false;
              const busy = busyId === req.id;
              return (
                <Panel
                  key={req.id}
                  title={`${req.document_no} · ${req.priority}`}
                  subtitle={`${req.lines.length} partida(s) · recibida ${formatDate(req.submitted_at ?? req.created_at)}`}
                  icon="approve"
                >
                  <div className="detail-grid compact">
                    <div><span>Prioridad</span><strong><PriorityBadge priority={req.priority} /></strong></div>
                    <div><span>Estado</span><strong><StatusBadge status={req.status} /></strong></div>
                    <div><span>Departamento</span><strong>{catalogLabel('departments', req.department_id)}</strong></div>
                    <div><span>Almacén</span><strong>{catalogLabel('warehouses', req.warehouse_id)}</strong></div>
                    <div><span>Equipo</span><strong>{catalogLabel('equipment', req.equipment_id)}</strong></div>
                    <div><span>Centro de costo</span><strong>{catalogLabel('cost_centers', req.cost_center_id)}</strong></div>
                    <div><span>Fecha requerida</span><strong>{formatDate(req.needed_at)}</strong></div>
                    <div><span>Orden de trabajo</span><strong>{req.work_order_no ?? '—'}</strong></div>
                    <div><span>Solicitante</span><strong>No disponible en la API actual</strong></div>
                    <div><span>Observaciones</span><strong>{req.observations ?? '—'}</strong></div>
                  </div>
                  <p className="justification">{req.justification}</p>
                  <div className="toolbar">
                    <button
                      className="button button-small button-ghost"
                      type="button"
                      onClick={() => setExpanded((state) => ({ ...state, [req.id]: !isOpen }))}
                    >
                      {isOpen ? 'Ocultar partidas' : 'Ver partidas'}
                    </button>
                    <button className="button button-small button-ghost" type="button" onClick={() => setAll(req.id, true)}>
                      Seleccionar todas
                    </button>
                    <button className="button button-small button-ghost" type="button" onClick={() => setAll(req.id, false)}>
                      Seleccionar ninguna
                    </button>
                    <button className="button button-small button-ghost" type="button" onClick={() => void handleHistory(req)}>
                      Historial
                    </button>
                  </div>

                  {isOpen && (
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Incluir</th>
                            <th>#</th>
                            <th>Artículo</th>
                            <th>Solicitada</th>
                            <th>Autorizar</th>
                            <th>Motivo por partida</th>
                            <th>UOM</th>
                            <th>Notas</th>
                          </tr>
                        </thead>
                        <tbody>
                          {req.lines.map((line) => {
                            const choice = current[line.id] ?? {
                              selected: true,
                              quantity: line.requested_qty,
                              reason: '',
                            };
                            const errorQty = quantityError(choice, line);
                            return (
                              <tr key={line.id} className={errorQty && choice.selected ? 'row-invalid' : undefined}>
                                <td>
                                  <input
                                    type="checkbox"
                                    aria-label={`Incluir partida ${line.line_no}`}
                                    checked={choice.selected}
                                    onChange={(event) => updateChoice(req.id, line.id, { selected: event.target.checked })}
                                  />
                                </td>
                                <td>{line.line_no}</td>
                                <td>{line.description}</td>
                                <td>{formatNumber(line.requested_qty)}</td>
                                <td>
                                  <input
                                    type="number"
                                    min="0"
                                    step="any"
                                    aria-label={`Cantidad a autorizar de la partida ${line.line_no}`}
                                    value={choice.quantity}
                                    onChange={(event) => updateChoice(req.id, line.id, { quantity: event.target.value })}
                                  />
                                  <InlineFieldError message={choice.selected ? errorQty : null} />
                                </td>
                                <td>
                                  <input
                                    aria-label={`Motivo de la partida ${line.line_no}`}
                                    value={choice.reason}
                                    onChange={(event) => updateChoice(req.id, line.id, { reason: event.target.value })}
                                  />
                                </td>
                                <td>{uomLabel(line.uom_id)}</td>
                                <td>{line.notes ?? '—'}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {history?.id === req.id && (
                    <Panel title={`Historial de ${req.document_no}`} icon="history">
                      {history.events.length === 0 ? (
                        <EmptyState text="Sin eventos registrados." />
                      ) : (
                        <ol className="timeline">
                          {history.events.map((event, index) => (
                            <li key={index}>
                              <strong>{event.event_type.replaceAll('_', ' ')}</strong>
                              <span>{event.from_status ?? '—'} → {event.to_status ?? '—'}</span>
                              <small>{formatDate(event.occurred_at)} · Actor {event.actor_id?.slice(0, 8) ?? 'sistema'}</small>
                            </li>
                          ))}
                        </ol>
                      )}
                    </Panel>
                  )}

                  <div className="form-actions">
                    {(Object.keys(MODE_LABELS) as DecisionMode[]).map((mode) => (
                      <button
                        key={mode}
                        className={`button ${mode.startsWith('REJECT') ? 'button-danger' : mode === 'APPROVE_ALL' ? 'button-primary' : 'button-secondary'}`}
                        type="button"
                        disabled={busy}
                        onClick={() => requestDecide(req, mode)}
                      >
                        {busy ? 'Registrando…' : MODE_LABELS[mode].label}
                      </button>
                    ))}
                  </div>
                </Panel>
              );
            })
          )}
        </>
      )}

      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.confirmLabel}
          onCancel={() => setConfirm(null)}
          onConfirm={() => {
            const action = confirm.onConfirm;
            setConfirm(null);
            action();
          }}
        />
      )}
    </>
  );
}
