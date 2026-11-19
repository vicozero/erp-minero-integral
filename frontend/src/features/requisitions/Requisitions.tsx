import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../../api/client';
import type {
  Catalogs,
  HistoryEvent,
  Requisition,
  RequisitionAttachment,
  RequisitionFilters,
  RequisitionPayload,
} from '../../api/types';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  PageHeader,
  Panel,
  StatusBadge,
  SuccessMessage,
} from '../../components/ui';

interface DraftLine {
  item_id: string;
  description: string;
  uom_id: string;
  requested_qty: string;
  notes: string;
}

const PRIORITIES: Array<{ value: RequisitionPayload['priority']; label: string }> = [
  { value: 'NORMAL', label: 'Normal' },
  { value: 'HIGH', label: 'Alta' },
  { value: 'URGENT', label: 'Crítica' },
];

function emptyLine(catalogs: Catalogs | null): DraftLine {
  return {
    item_id: catalogs?.items[0]?.id ?? '',
    description: catalogs?.items[0]?.name ?? '',
    uom_id: catalogs?.uoms[0]?.id ?? '',
    requested_qty: '1',
    notes: '',
  };
}

export function Requisitions() {
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [sending, setSending] = useState(false);
  const [history, setHistory] = useState<{ id: string; events: HistoryEvent[] } | null>(null);
  const [attachmentPanel, setAttachmentPanel] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<RequisitionAttachment[]>([]);
  const [filters, setFilters] = useState<RequisitionFilters>({});

  const [departmentId, setDepartmentId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [costCenterId, setCostCenterId] = useState('');
  const [requisitionType, setRequisitionType] = useState<RequisitionPayload['requisition_type']>('STOCK');
  const [priority, setPriority] = useState<RequisitionPayload['priority']>('NORMAL');
  const [justification, setJustification] = useState('');
  const [observations, setObservations] = useState('');
  const [neededAt, setNeededAt] = useState('');
  const [workOrderNo, setWorkOrderNo] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([]);

  async function reload(nextFilters: RequisitionFilters = filters) {
    setRequisitions(await api.requisitions(nextFilters));
  }

  useEffect(() => {
    Promise.all([api.catalogs(), api.requisitions()])
      .then(([catalogData, requisitionData]) => {
        setCatalogs(catalogData);
        setRequisitions(requisitionData);
        setDepartmentId(catalogData.departments[0]?.id ?? '');
        setWarehouseId(catalogData.warehouses[0]?.id ?? '');
        setEquipmentId(catalogData.equipment[0]?.id ?? '');
        setCostCenterId(catalogData.cost_centers[0]?.id ?? '');
        setLines([emptyLine(catalogData)]);
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Error al cargar.'));
  }, []);

  function updateLine(index: number, patch: Partial<DraftLine>) {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  async function handleCreate(event: FormEvent, submitAfter: boolean) {
    event.preventDefault();
    if (sending) return;
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      const payload: RequisitionPayload = {
        department_id: departmentId,
        warehouse_id: warehouseId || null,
        equipment_id: equipmentId || null,
        cost_center_id: costCenterId,
        requisition_type: requisitionType,
        priority,
        justification,
        observations: observations || null,
        needed_at: neededAt ? new Date(neededAt).toISOString() : null,
        work_order_no: workOrderNo || null,
        lines: lines.map((line) => ({
          item_id: line.item_id || null,
          description: line.description,
          uom_id: line.uom_id,
          requested_qty: line.requested_qty,
          notes: line.notes || null,
        })),
      };
      const created = await api.createRequisition(payload);
      if (submitAfter) {
        await api.submitRequisition(created.id);
      }
      setNotice(
        submitAfter
          ? `Requisición ${created.document_no} creada y enviada a autorización.`
          : `Borrador ${created.document_no} guardado.`,
      );
      setShowForm(false);
      setJustification('');
      setObservations('');
      setNeededAt('');
      setWorkOrderNo('');
      if (catalogs) setLines([emptyLine(catalogs)]);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible guardar.');
    } finally {
      setSending(false);
    }
  }

  async function handleAction(action: () => Promise<Requisition>, message: string) {
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      await action();
      setNotice(message);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible completar la acción.');
    } finally {
      setSending(false);
    }
  }

  async function handleHistory(id: string) {
    setError(null);
    try {
      setHistory({ id, events: await api.history(id) });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible cargar el historial.');
    }
  }

  async function handleAttachments(id: string) {
    setError(null);
    try {
      setAttachments(await api.attachments(id));
      setAttachmentPanel(id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible cargar los adjuntos.');
    }
  }

  async function handleUpload(id: string, file: File | undefined) {
    if (!file) return;
    setError(null);
    setSending(true);
    try {
      await api.uploadAttachment(id, file);
      setAttachments(await api.attachments(id));
      setNotice('Adjunto registrado con verificador SHA-256.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible adjuntar el archivo.');
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHeader title="Requisiciones" subtitle="Captura, autorización, reservas y seguimiento por partida" />
      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />
      <div className="toolbar">
        <button className="button button-primary" type="button" onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Ocultar formulario' : 'Nueva requisición'}
        </button>
      </div>

      {showForm && catalogs && (
        <Panel title="Captura de requisición">
          <form onSubmit={(event) => handleCreate(event, false)}>
            <div className="grid-3">
              <label>Departamento
                <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
                  {catalogs.departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <label>Almacén
                <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                  {catalogs.warehouses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <label>Centro de costo
                <select value={costCenterId} onChange={(e) => setCostCenterId(e.target.value)}>
                  {catalogs.cost_centers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <label>Equipo
                <select value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)}>
                  {catalogs.equipment.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                </select>
              </label>
              <label>Tipo
                <select
                  value={requisitionType}
                  onChange={(e) => setRequisitionType(e.target.value as RequisitionPayload['requisition_type'])}
                >
                  <option value="STOCK">Almacén</option>
                  <option value="PURCHASE">Compra directa</option>
                  <option value="SERVICE">Servicio</option>
                </select>
              </label>
              <label>Prioridad
                <select value={priority} onChange={(e) => setPriority(e.target.value as RequisitionPayload['priority'])}>
                  {PRIORITIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <label>Fecha requerida
                <input type="datetime-local" value={neededAt} onChange={(e) => setNeededAt(e.target.value)} />
              </label>
              <label>Orden de trabajo (GMAO)
                <input
                  value={workOrderNo}
                  maxLength={80}
                  placeholder="Referencia externa opcional"
                  onChange={(e) => setWorkOrderNo(e.target.value)}
                />
              </label>
            </div>
            <label>Justificación
              <textarea value={justification} onChange={(e) => setJustification(e.target.value)} required minLength={4} />
            </label>
            <label>Observaciones
              <input value={observations} onChange={(e) => setObservations(e.target.value)} maxLength={1000} />
            </label>

            <h3>Partidas consecutivas</h3>
            {lines.map((line, index) => (
              <div className="line-editor" key={index}>
                <label>Artículo
                  <select
                    value={line.item_id}
                    onChange={(e) => {
                      const item = catalogs.items.find((candidate) => candidate.id === e.target.value);
                      updateLine(index, { item_id: e.target.value, description: item?.name ?? line.description });
                    }}
                  >
                    {catalogs.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
                  </select>
                </label>
                <label>Descripción
                  <input value={line.description} onChange={(e) => updateLine(index, { description: e.target.value })} />
                </label>
                <label>Unidad
                  <select value={line.uom_id} onChange={(e) => updateLine(index, { uom_id: e.target.value })}>
                    {catalogs.uoms.map((uom) => <option key={uom.id} value={uom.id}>{uom.code}</option>)}
                  </select>
                </label>
                <label>Cantidad solicitada
                  <input
                    type="number"
                    min="0.000001"
                    step="any"
                    value={line.requested_qty}
                    onChange={(e) => updateLine(index, { requested_qty: e.target.value })}
                  />
                </label>
                <label>Notas
                  <input value={line.notes} onChange={(e) => updateLine(index, { notes: e.target.value })} />
                </label>
                {lines.length > 1 && (
                  <button
                    type="button"
                    className="button button-ghost"
                    onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
                  >
                    Quitar
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              className="button button-ghost"
              onClick={() => setLines((current) => [...current, emptyLine(catalogs)])}
            >
              Agregar partida
            </button>
            <div className="form-actions">
              <button className="button button-secondary" type="submit" disabled={sending}>Guardar borrador</button>
              <button
                className="button button-primary"
                type="button"
                disabled={sending}
                onClick={(event) => handleCreate(event, true)}
              >
                Guardar y enviar
              </button>
            </div>
          </form>
        </Panel>
      )}

      <Panel title="Filtros de seguimiento">
        <div className="grid-3">
          <label>Folio
            <input value={filters.document_no ?? ''} onChange={(e) => setFilters({ ...filters, document_no: e.target.value })} />
          </label>
          <label>Estado
            <select value={filters.status ?? ''} onChange={(e) => setFilters({ ...filters, status: e.target.value || undefined })}>
              <option value="">Todos</option>
              {['DRAFT', 'SUBMITTED', 'APPROVED', 'PARTIALLY_APPROVED', 'REJECTED', 'CANCELLED', 'IN_PROGRESS', 'CLOSED'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>Prioridad
            <select value={filters.priority ?? ''} onChange={(e) => setFilters({ ...filters, priority: e.target.value || undefined })}>
              <option value="">Todas</option>
              {PRIORITIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
            </select>
          </label>
          <label>Departamento
            <select
              value={filters.department_id ?? ''}
              onChange={(e) => setFilters({ ...filters, department_id: e.target.value || undefined })}
            >
              <option value="">Todos</option>
              {catalogs?.departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>Equipo
            <select
              value={filters.equipment_id ?? ''}
              onChange={(e) => setFilters({ ...filters, equipment_id: e.target.value || undefined })}
            >
              <option value="">Todos</option>
              {catalogs?.equipment.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>Desde
            <input type="datetime-local" value={filters.date_from ?? ''} onChange={(e) => setFilters({ ...filters, date_from: e.target.value || undefined })} />
          </label>
          <label>Hasta
            <input type="datetime-local" value={filters.date_to ?? ''} onChange={(e) => setFilters({ ...filters, date_to: e.target.value || undefined })} />
          </label>
        </div>
        <div className="form-actions">
          <button className="button button-primary" type="button" disabled={sending} onClick={() => reload()}>
            Aplicar filtros
          </button>
          <button
            className="button button-ghost"
            type="button"
            onClick={() => {
              const empty: RequisitionFilters = {};
              setFilters(empty);
              reload(empty);
            }}
          >
            Limpiar
          </button>
        </div>
      </Panel>

      <Panel title="Listado de requisiciones">
        {requisitions.length === 0 ? (
          <EmptyState text="No hay requisiciones registradas." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Folio</th><th>Estado</th><th>Prioridad</th><th>OT</th><th>Partidas</th><th>Justificación</th><th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {requisitions.map((req) => (
                  <tr key={req.id}>
                    <td>{req.document_no}</td>
                    <td><StatusBadge status={req.status} /></td>
                    <td>{PRIORITIES.find((p) => p.value === req.priority)?.label ?? req.priority}</td>
                    <td>{req.work_order_no ?? '—'}</td>
                    <td>{req.lines.length}</td>
                    <td>{req.justification}</td>
                    <td className="actions">
                      {req.status === 'DRAFT' && (
                        <button
                          className="button button-small"
                          type="button"
                          disabled={sending}
                          onClick={() => handleAction(() => api.submitRequisition(req.id), `${req.document_no} enviada a autorización.`)}
                        >
                          Enviar
                        </button>
                      )}
                      {!['CANCELLED', 'CLOSED', 'REJECTED'].includes(req.status) && (
                        <button
                          className="button button-small button-ghost"
                          type="button"
                          disabled={sending}
                          onClick={() => {
                            const reason = window.prompt('Motivo de la cancelación (mínimo 4 caracteres):');
                            if (reason) {
                              handleAction(() => api.cancelRequisition(req.id, reason), `${req.document_no} cancelada.`);
                            }
                          }}
                        >
                          Cancelar
                        </button>
                      )}
                      <button className="button button-small button-ghost" type="button" onClick={() => handleAttachments(req.id)}>
                        Adjuntos
                      </button>
                      <button className="button button-small button-ghost" type="button" onClick={() => handleHistory(req.id)}>
                        Seguimiento
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {attachmentPanel && (
        <Panel title={`Adjuntos de ${requisitions.find((r) => r.id === attachmentPanel)?.document_no ?? ''}`}>
          <input
            type="file"
            accept=".pdf,.jpg,.jpeg,.png"
            disabled={sending}
            onChange={(e) => handleUpload(attachmentPanel, e.target.files?.[0])}
          />
          {attachments.length === 0 ? (
            <EmptyState text="Sin adjuntos registrados." />
          ) : (
            <ul>
              {attachments.map((attachment) => (
                <li key={attachment.id}>
                  <a href={api.attachmentUrl(attachmentPanel, attachment.id)} target="_blank" rel="noreferrer">
                    {attachment.file_name}
                  </a>{' '}
                  <small>{attachment.size_bytes} bytes · SHA-256 {attachment.sha256.slice(0, 12)}…</small>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      {history && (
        <Panel title={`Seguimiento de ${history.id.slice(0, 8)}`}>
          {history.events.length === 0 ? (
            <EmptyState text="Sin eventos registrados." />
          ) : (
            <ol className="timeline">
              {history.events.map((event, index) => (
                <li key={index}>
                  <strong>{event.event_type.replaceAll('_', ' ')}</strong>
                  <span>{event.from_status ?? '—'} → {event.to_status ?? '—'}</span>
                  <small>{new Date(event.occurred_at).toLocaleString('es-MX')}</small>
                </li>
              ))}
            </ol>
          )}
        </Panel>
      )}

      {requisitions.length > 0 && (
        <Panel title="Control de cantidades por partida">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Requisición</th><th>Partida</th><th>Solicitada</th><th>Autorizada</th>
                  <th>Reservada</th><th>Comprada</th><th>Recibida</th><th>Entregada</th><th>Pendiente</th>
                </tr>
              </thead>
              <tbody>
                {requisitions.flatMap((req) =>
                  req.lines.map((line) => (
                    <tr key={`${req.id}-${line.id}`}>
                      <td>{req.document_no}</td>
                      <td>{line.line_no}</td>
                      <td>{formatNumber(line.requested_qty)}</td>
                      <td>{formatNumber(line.authorised_qty)}</td>
                      <td>{formatNumber(line.reserved_qty)}</td>
                      <td>{formatNumber(line.purchased_qty)}</td>
                      <td>{formatNumber(line.received_qty)}</td>
                      <td>{formatNumber(line.delivered_qty)}</td>
                      <td>{formatNumber(line.pending_qty)}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  );
}
