import { useEffect, useState, type FormEvent } from 'react';
import { api, describeApiError } from '../../api/client';
import type {
  Catalogs,
  HistoryEvent,
  Requisition,
  RequisitionAttachment,
  RequisitionDraftUpdatePayload,
  RequisitionFilters,
  RequisitionPayload,
  SlaEvaluation,
  WmsItem,
} from '../../api/types';
import { ItemPicker } from '../../components/ItemPicker';
import {
  ConfirmDialog,
  EmptyState,
  ErrorMessage,
  formatNumber,
  InlineFieldError,
  LineQuantitiesTable,
  LoadingState,
  PageHeader,
  Panel,
  PriorityBadge,
  SlaBadge,
  StatusBadge,
  SuccessMessage,
} from '../../components/ui';

interface DraftLine {
  id?: string;
  item_id: string;
  item_code: string;
  description: string;
  part_no: string;
  uom_id: string;
  uom_code: string;
  requested_qty: string;
  notes: string;
}

interface ConfirmState {
  title: string;
  message: string;
  confirmLabel: string;
  needsReason?: boolean;
  reasonLabel?: string;
  onConfirm: (reason: string) => void;
}

const PRIORITIES: Array<{ value: RequisitionPayload['priority']; label: string }> = [
  { value: 'LOW', label: 'Baja' },
  { value: 'NORMAL', label: 'Normal' },
  { value: 'HIGH', label: 'Alta' },
  { value: 'URGENT', label: 'Crítica' },
];

const REQUISITION_TYPES: Array<{ value: RequisitionPayload['requisition_type']; label: string }> = [
  { value: 'STOCK', label: 'Almacén' },
  { value: 'PURCHASE', label: 'Compra directa' },
  { value: 'SERVICE', label: 'Servicio' },
];

const SLA_FILTERS: Array<{
  value: NonNullable<RequisitionFilters['sla_color']>;
  label: string;
}> = [
  { value: 'GREEN', label: 'En plazo' },
  { value: 'YELLOW', label: 'En riesgo' },
  { value: 'RED', label: 'Fuera de plazo' },
  { value: 'NONE', label: 'Sin medición' },
];

function emptyLine(catalogs: Catalogs | null): DraftLine {
  return {
    item_id: '',
    item_code: '',
    description: '',
    part_no: '',
    uom_id: catalogs?.uoms[0]?.id ?? '',
    uom_code: catalogs?.uoms[0]?.code ?? '',
    requested_qty: '1',
    notes: '',
  };
}

function lineFromRequisition(line: Requisition['lines'][number]): DraftLine {
  return {
    id: line.id,
    item_id: line.item_id ?? '',
    item_code: '',
    description: line.description,
    part_no: '',
    uom_id: line.uom_id,
    uom_code: '',
    requested_qty: line.requested_qty,
    notes: line.notes ?? '',
  };
}

function shortId(value: string | null | undefined): string {
  return value ? value.slice(0, 8) : 'sistema';
}

function formatDate(value: string | null): string {
  return value ? new Date(value).toLocaleString('es-MX') : '—';
}

export function Requisitions() {
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [sending, setSending] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [editingDraftId, setEditingDraftId] = useState<string | null>(null);
  const [history, setHistory] = useState<{ documentNo: string; events: HistoryEvent[] } | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [slaHistory, setSlaHistory] = useState<{ documentNo: string; events: SlaEvaluation[] } | null>(null);
  const [slaHistoryLoading, setSlaHistoryLoading] = useState(false);
  const [attachmentPanel, setAttachmentPanel] = useState<string | null>(null);
  const [attachments, setAttachments] = useState<RequisitionAttachment[]>([]);
  const [filters, setFilters] = useState<RequisitionFilters>({});
  const [selectedDetail, setSelectedDetail] = useState<string | null>(null);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [pickerLine, setPickerLine] = useState<number | null>(null);

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

  function resetForm(data: Catalogs | null = catalogs): void {
    setDepartmentId(data?.departments[0]?.id ?? '');
    setWarehouseId(data?.warehouses[0]?.id ?? '');
    setEquipmentId('');
    setCostCenterId(data?.cost_centers[0]?.id ?? '');
    setRequisitionType('STOCK');
    setPriority('NORMAL');
    setJustification('');
    setObservations('');
    setNeededAt('');
    setWorkOrderNo('');
    setLines([emptyLine(data)]);
    setEditingDraftId(null);
    setFieldErrors({});
  }

  async function reload(nextFilters: RequisitionFilters = filters): Promise<void> {
    try {
      setRequisitions(await api.requisitions(nextFilters));
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible actualizar el listado.'));
    }
  }

  useEffect(() => {
    let active = true;
    Promise.all([api.catalogs(), api.requisitions()])
      .then(([catalogData, requisitionData]) => {
        if (!active) return;
        setCatalogs(catalogData);
        setRequisitions(requisitionData);
        resetForm(catalogData);
      })
      .catch((cause: unknown) => {
        if (active) setError(describeApiError(cause, 'No fue posible cargar la pantalla.'));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
    // resetForm usa el estado de catálogos que se entrega explícitamente.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function updateLine(index: number, patch: Partial<DraftLine>): void {
    setLines((current) => current.map((line, i) => (i === index ? { ...line, ...patch } : line)));
  }

  function selectItem(index: number, item: WmsItem): void {
    updateLine(index, {
      item_id: item.id,
      item_code: item.code,
      description: item.description,
      part_no: item.manufacturer_part_no ?? '',
      uom_id: item.uom_id,
      uom_code: item.uom_code,
    });
    setPickerLine(null);
    setFieldErrors((current) => {
      const next = { ...current };
      delete next[`line-${index}-description`];
      return next;
    });
  }

  function validate(): boolean {
    const next: Record<string, string> = {};
    if (!departmentId) next.department = 'Seleccione un departamento.';
    if (!costCenterId) next.costCenter = 'Seleccione un centro de costo.';
    if (requisitionType === 'STOCK' && !warehouseId) next.warehouse = 'El tipo Almacén requiere un almacén.';
    if (justification.trim().length < 4) next.justification = 'Indique una justificación de al menos 4 caracteres.';
    lines.forEach((line, index) => {
      if (line.description.trim().length < 2) {
        next[`line-${index}-description`] = 'La descripción debe tener al menos 2 caracteres.';
      }
      if (!line.uom_id) next[`line-${index}-uom`] = 'Seleccione una unidad.';
      const qty = Number(line.requested_qty);
      if (!Number.isFinite(qty) || qty <= 0) {
        next[`line-${index}-qty`] = 'La cantidad debe ser mayor a cero.';
      }
    });
    setFieldErrors(next);
    return Object.keys(next).length === 0;
  }

  function buildPayload(): RequisitionPayload {
    return {
      department_id: departmentId,
      warehouse_id: warehouseId || null,
      equipment_id: equipmentId || null,
      cost_center_id: costCenterId,
      requisition_type: requisitionType,
      priority,
      justification: justification.trim(),
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
  }

  function buildDraftPayload(): RequisitionDraftUpdatePayload {
    return {
      justification: justification.trim(),
      priority,
      observations: observations || null,
      needed_at: neededAt ? new Date(neededAt).toISOString() : null,
      work_order_no: workOrderNo || null,
      lines: lines.map((line) => ({
        ...(line.id ? { id: line.id } : {}),
        item_id: line.item_id || null,
        description: line.description,
        uom_id: line.uom_id,
        requested_qty: line.requested_qty,
        notes: line.notes || null,
      })),
    };
  }

  async function runSave(submitAfter: boolean): Promise<void> {
    if (sending || !validate()) return;
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      const saved = editingDraftId
        ? await api.updateRequisitionDraft(editingDraftId, buildDraftPayload())
        : await api.createRequisition(buildPayload());
      if (submitAfter) await api.submitRequisition(saved.id);
      setNotice(
        submitAfter
          ? `Requisición ${saved.document_no} creada y enviada a autorización.`
          : `Borrador ${saved.document_no} guardado correctamente.`,
      );
      setShowForm(false);
      resetForm();
      await reload();
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible guardar la requisición.'));
    } finally {
      setSending(false);
    }
  }

  function askSubmit(event: FormEvent): void {
    event.preventDefault();
    if (!validate()) return;
    setConfirm({
      title: 'Enviar a autorización',
      message: 'El documento quedará bloqueado para edición y será enviado a la bandeja de autorizaciones.',
      confirmLabel: 'Enviar requisición',
      onConfirm: () => void runSave(true),
    });
  }

  async function handleAction(action: () => Promise<Requisition>, message: string): Promise<void> {
    if (sending) return;
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      await action();
      setNotice(message);
      await reload();
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible completar la acción.'));
    } finally {
      setSending(false);
    }
  }

  async function handleHistory(req: Requisition): Promise<void> {
    setHistoryLoading(true);
    setError(null);
    try {
      setHistory({ documentNo: req.document_no, events: await api.history(req.id) });
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible cargar el historial.'));
    } finally {
      setHistoryLoading(false);
    }
  }

  async function handleSlaHistory(req: Requisition): Promise<void> {
    setSlaHistoryLoading(true);
    setError(null);
    try {
      setSlaHistory({ documentNo: req.document_no, events: await api.slaHistory(req.id) });
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible cargar el historial SLA.'));
    } finally {
      setSlaHistoryLoading(false);
    }
  }

  async function handleAttachments(id: string): Promise<void> {
    setError(null);
    try {
      setAttachments(await api.attachments(id));
      setAttachmentPanel(id);
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible cargar los adjuntos.'));
    }
  }

  async function handleUpload(id: string, file: File | undefined): Promise<void> {
    if (!file) return;
    setError(null);
    setSending(true);
    try {
      await api.uploadAttachment(id, file);
      setAttachments(await api.attachments(id));
      setNotice('Adjunto registrado con verificador SHA-256.');
    } catch (cause) {
      setError(describeApiError(cause, 'No fue posible adjuntar el archivo.'));
    } finally {
      setSending(false);
    }
  }

  function openEditor(req: Requisition): void {
    setDepartmentId(req.department_id);
    setWarehouseId(req.warehouse_id ?? '');
    setEquipmentId(req.equipment_id ?? '');
    setCostCenterId(req.cost_center_id);
    setRequisitionType(req.requisition_type as RequisitionPayload['requisition_type']);
    setPriority(req.priority as RequisitionPayload['priority']);
    setJustification(req.justification);
    setObservations(req.observations ?? '');
    setNeededAt(req.needed_at ? req.needed_at.slice(0, 16) : '');
    setWorkOrderNo(req.work_order_no ?? '');
    setLines(req.lines.filter((line) => line.status !== 'CANCELLED').map(lineFromRequisition));
    setEditingDraftId(req.id);
    setFieldErrors({});
    setShowForm(true);
  }

  const lineSummary = lines.reduce<Record<string, { count: number; quantity: number }>>((acc, line) => {
    const key = line.uom_code || 'UOM';
    const current = acc[key] ?? { count: 0, quantity: 0 };
    acc[key] = { count: current.count + 1, quantity: current.quantity + (Number(line.requested_qty) || 0) };
    return acc;
  }, {});
  const detailReq = requisitions.find((req) => req.id === selectedDetail) ?? null;
  const attachmentReq = requisitions.find((req) => req.id === attachmentPanel) ?? null;

  return (
    <>
      <PageHeader
        title="Requisiciones"
        subtitle="Captura guiada, borradores, autorización y seguimiento por partida"
        actions={
          <button
            className="button button-primary"
            type="button"
            onClick={() => {
              if (showForm) {
                setShowForm(false);
                setEditingDraftId(null);
              } else {
                resetForm();
                setShowForm(true);
              }
            }}
          >
            {showForm ? 'Ocultar formulario' : 'Nueva requisición'}
          </button>
        }
      />
      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />

      {loading ? (
        <Panel title="Cargando requisiciones" icon="requisitions">
          <LoadingState rows={5} />
        </Panel>
      ) : (
        <>
          {showForm && catalogs && (
            <Panel
              title={editingDraftId ? 'Editar borrador' : 'Captura de requisición'}
              subtitle="Las cantidades y estados de surtido se calculan en el servidor; aquí solo se captura la solicitud."
              icon="requisitions"
            >
              <form onSubmit={askSubmit} noValidate>
                <div className="grid-3">
                  <label>
                    Departamento *
                    <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
                      <option value="">Seleccione…</option>
                      {catalogs.departments.map((item) => (
                        <option key={item.id} value={item.id}>{item.name ?? item.code}</option>
                      ))}
                    </select>
                    <InlineFieldError message={fieldErrors.department} />
                  </label>
                  <label>
                    Almacén {requisitionType === 'STOCK' && '*'}
                    <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                      <option value="">Sin almacén</option>
                      {catalogs.warehouses.map((item) => (
                        <option key={item.id} value={item.id}>{item.name ?? item.code}</option>
                      ))}
                    </select>
                    <InlineFieldError message={fieldErrors.warehouse} />
                  </label>
                  <label>
                    Centro de costo *
                    <select value={costCenterId} onChange={(e) => setCostCenterId(e.target.value)}>
                      <option value="">Seleccione…</option>
                      {catalogs.cost_centers.map((item) => (
                        <option key={item.id} value={item.id}>{item.name ?? item.code}</option>
                      ))}
                    </select>
                    <InlineFieldError message={fieldErrors.costCenter} />
                  </label>
                  <label>
                    Equipo
                    <select value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)}>
                      <option value="">Sin equipo</option>
                      {catalogs.equipment.map((item) => (
                        <option key={item.id} value={item.id}>{item.name ?? item.code}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Tipo de requisición
                    <select
                      value={requisitionType}
                      onChange={(e) => setRequisitionType(e.target.value as RequisitionPayload['requisition_type'])}
                    >
                      {REQUISITION_TYPES.map((item) => (
                        <option key={item.value} value={item.value}>{item.label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Prioridad
                    <select value={priority} onChange={(e) => setPriority(e.target.value as RequisitionPayload['priority'])}>
                      {PRIORITIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                    </select>
                  </label>
                  <label>
                    Fecha requerida
                    <input type="datetime-local" value={neededAt} onChange={(e) => setNeededAt(e.target.value)} />
                  </label>
                  <label>
                    Orden de trabajo (GMAO)
                    <input
                      value={workOrderNo}
                      maxLength={80}
                      placeholder="Referencia externa opcional"
                      onChange={(e) => setWorkOrderNo(e.target.value)}
                    />
                  </label>
                </div>
                <label>
                  Justificación *
                  <textarea
                    value={justification}
                    onChange={(e) => setJustification(e.target.value)}
                    maxLength={1000}
                    rows={2}
                  />
                  <InlineFieldError message={fieldErrors.justification} />
                </label>
                <label>
                  Observaciones
                  <input value={observations} onChange={(e) => setObservations(e.target.value)} maxLength={1000} />
                </label>

                <h3>Partidas</h3>
                <div className="chip-row">
                  {lines.length === 0 ? (
                    <span className="hint">Agregue al menos una partida.</span>
                  ) : (
                    Object.entries(lineSummary).map(([uom, summary]) => (
                      <span className="chip" key={uom}>
                        {uom}: {formatNumber(summary.quantity)} ({summary.count} {summary.count === 1 ? 'partida' : 'partidas'})
                      </span>
                    ))
                  )}
                </div>
                {lines.map((line, index) => (
                  <div className="line-editor" key={line.id ?? `new-${index}`}>
                    <div className="line-editor-header">
                      <strong>Partida {index + 1}</strong>
                      {line.item_code && <span className="chip">{line.item_code}</span>}
                      {line.part_no && <span className="chip">Parte {line.part_no}</span>}
                    </div>
                    <label>
                      Artículo
                      <input value={line.description} readOnly placeholder="Seleccione desde el catálogo" />
                      <button
                        className="button button-small button-secondary"
                        type="button"
                        onClick={() => setPickerLine(index)}
                      >
                        {line.item_id ? 'Cambiar artículo' : 'Seleccionar artículo'}
                      </button>
                      <InlineFieldError message={fieldErrors[`line-${index}-description`]} />
                    </label>
                    <label>
                      Descripción libre
                      <input
                        value={line.description}
                        onChange={(e) => updateLine(index, { description: e.target.value })}
                        maxLength={255}
                      />
                    </label>
                    <label>
                      Unidad
                      <select value={line.uom_id} onChange={(e) => {
                        const uom = catalogs.uoms.find((candidate) => candidate.id === e.target.value);
                        updateLine(index, { uom_id: e.target.value, uom_code: uom?.code ?? '' });
                      }}>
                        <option value="">Seleccione…</option>
                        {catalogs.uoms.map((uom) => <option key={uom.id} value={uom.id}>{uom.code}</option>)}
                      </select>
                      <InlineFieldError message={fieldErrors[`line-${index}-uom`]} />
                    </label>
                    <label>
                      Cantidad solicitada
                      <input
                        type="number"
                        min="0.000001"
                        step="any"
                        value={line.requested_qty}
                        onChange={(e) => updateLine(index, { requested_qty: e.target.value })}
                      />
                      <InlineFieldError message={fieldErrors[`line-${index}-qty`]} />
                    </label>
                    <label>
                      Notas
                      <input value={line.notes} maxLength={500} onChange={(e) => updateLine(index, { notes: e.target.value })} />
                    </label>
                    {lines.length > 1 && (
                      <button
                        type="button"
                        className="button button-ghost"
                        onClick={() => setLines((current) => current.filter((_, i) => i !== index))}
                      >
                        Quitar partida
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
                  <button className="button button-secondary" type="button" disabled={sending} onClick={() => void runSave(false)}>
                    {editingDraftId ? 'Actualizar borrador' : 'Guardar borrador'}
                  </button>
                  <button className="button button-primary" type="submit" disabled={sending}>
                    Guardar y enviar
                  </button>
                  {editingDraftId && (
                    <button className="button button-ghost" type="button" onClick={() => resetForm()}>
                      Cancelar edición
                    </button>
                  )}
                </div>
              </form>
            </Panel>
          )}

          <Panel title="Filtros de seguimiento" icon="search">
            <div className="grid-3">
              <label>
                Folio
                <input value={filters.document_no ?? ''} onChange={(e) => setFilters({ ...filters, document_no: e.target.value })} />
              </label>
              <label>
                Estado
                <select value={filters.status ?? ''} onChange={(e) => setFilters({ ...filters, status: e.target.value || undefined })}>
                  <option value="">Todos</option>
                  {['DRAFT', 'SUBMITTED', 'APPROVED', 'PARTIALLY_APPROVED', 'REJECTED', 'CANCELLED', 'IN_PROGRESS', 'CLOSED'].map((status) => (
                    <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>
                  ))}
                </select>
              </label>
              <label>
                Semáforo SLA
                <select
                  value={filters.sla_color ?? ''}
                  onChange={(e) => setFilters({
                    ...filters,
                    sla_color: (e.target.value || undefined) as RequisitionFilters['sla_color'],
                  })}
                >
                  <option value="">Todos</option>
                  {SLA_FILTERS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <label>
                Prioridad
                <select value={filters.priority ?? ''} onChange={(e) => setFilters({ ...filters, priority: e.target.value || undefined })}>
                  <option value="">Todas</option>
                  {PRIORITIES.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
                </select>
              </label>
              <label>
                Departamento
                <select
                  value={filters.department_id ?? ''}
                  onChange={(e) => setFilters({ ...filters, department_id: e.target.value || undefined })}
                >
                  <option value="">Todos</option>
                  {catalogs?.departments.map((item) => <option key={item.id} value={item.id}>{item.name ?? item.code}</option>)}
                </select>
              </label>
              <label>
                Equipo
                <select
                  value={filters.equipment_id ?? ''}
                  onChange={(e) => setFilters({ ...filters, equipment_id: e.target.value || undefined })}
                >
                  <option value="">Todos</option>
                  {catalogs?.equipment.map((item) => <option key={item.id} value={item.id}>{item.name ?? item.code}</option>)}
                </select>
              </label>
              <label>
                Desde
                <input type="date" value={filters.date_from ?? ''} onChange={(e) => setFilters({ ...filters, date_from: e.target.value || undefined })} />
              </label>
              <label>
                Hasta
                <input type="date" value={filters.date_to ?? ''} onChange={(e) => setFilters({ ...filters, date_to: e.target.value || undefined })} />
              </label>
            </div>
            <div className="form-actions">
              <button className="button button-primary" type="button" disabled={sending} onClick={() => void reload()}>
                Aplicar filtros
              </button>
              <button
                className="button button-ghost"
                type="button"
                onClick={() => {
                  const empty: RequisitionFilters = {};
                  setFilters(empty);
                  void reload(empty);
                }}
              >
                Limpiar
              </button>
            </div>
          </Panel>

          <Panel title="Listado de requisiciones" subtitle={`${requisitions.length} documento(s) en el alcance del usuario`} icon="requisitions">
            {requisitions.length === 0 ? (
              <EmptyState text="No hay requisiciones que coincidan con los filtros." />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Folio</th><th>Estado</th><th>Semáforo</th><th>Prioridad</th><th>Tipo</th>
                      <th>Partidas</th><th>Requerida</th><th>Justificación</th><th>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requisitions.map((req) => (
                      <tr key={req.id} className={selectedDetail === req.id ? 'row-selected' : undefined}>
                        <td><strong>{req.document_no}</strong></td>
                        <td><StatusBadge status={req.status} /></td>
                        <td><SlaBadge sla={req.sla} /></td>
                        <td><PriorityBadge priority={req.priority} /></td>
                        <td>{req.requisition_type}</td>
                        <td>{req.lines.length}</td>
                        <td>{formatDate(req.needed_at)}</td>
                        <td>{req.justification}</td>
                        <td className="actions">
                          <button
                            className="button button-small button-ghost"
                            type="button"
                            onClick={() => setSelectedDetail(selectedDetail === req.id ? null : req.id)}
                          >
                            Detalle
                          </button>
                          {req.status === 'DRAFT' && (
                            <>
                              <button
                                className="button button-small button-ghost"
                                type="button"
                                disabled={sending}
                                onClick={() => openEditor(req)}
                              >
                                Editar
                              </button>
                              <button
                                className="button button-small"
                                type="button"
                                disabled={sending}
                                onClick={() => setConfirm({
                                  title: 'Enviar a autorización',
                                  message: `${req.document_no} será enviada a la bandeja de autorizaciones.`,
                                  confirmLabel: 'Enviar',
                                  onConfirm: () => void handleAction(
                                    () => api.submitRequisition(req.id),
                                    `${req.document_no} enviada a autorización.`,
                                  ),
                                })}
                              >
                                Enviar
                              </button>
                            </>
                          )}
                          {!['CANCELLED', 'CLOSED', 'REJECTED'].includes(req.status) && (
                            <button
                              className="button button-small button-ghost"
                              type="button"
                              disabled={sending}
                              onClick={() => setConfirm({
                                title: 'Cancelar requisición',
                                message: `${req.document_no} quedará cancelada. Esta acción no se puede deshacer.`,
                                confirmLabel: 'Cancelar requisición',
                                needsReason: true,
                                reasonLabel: 'Motivo de la cancelación',
                                onConfirm: (reason) => void handleAction(
                                  () => api.cancelRequisition(req.id, reason),
                                  `${req.document_no} cancelada.`,
                                ),
                              })}
                            >
                              Cancelar
                            </button>
                          )}
                          <button className="button button-small button-ghost" type="button" onClick={() => void handleAttachments(req.id)}>
                            Adjuntos
                          </button>
                          <button className="button button-small button-ghost" type="button" onClick={() => void handleHistory(req)}>
                            Seguimiento
                          </button>
                          <button className="button button-small button-ghost" type="button" onClick={() => void handleSlaHistory(req)}>
                            Historial SLA
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {detailReq && (
            <Panel title={`Surtido de ${detailReq.document_no}`} subtitle="Cantidades derivadas del servidor" icon="box">
              <LineQuantitiesTable requisitions={[detailReq]} />
            </Panel>
          )}

          {attachmentReq && (
            <Panel title={`Adjuntos de ${attachmentReq.document_no}`} icon="requisitions">
              <p className="hint">Formatos PDF, JPG o PNG · máximo 5 MiB · se registra SHA-256.</p>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png"
                disabled={sending}
                onChange={(e) => void handleUpload(attachmentReq.id, e.target.files?.[0])}
              />
              {attachments.length === 0 ? (
                <EmptyState text="Sin adjuntos registrados." />
              ) : (
                <ul className="attachment-list">
                  {attachments.map((attachment) => (
                    <li key={attachment.id}>
                      <a href={api.attachmentUrl(attachmentReq.id, attachment.id)} target="_blank" rel="noreferrer">
                        {attachment.file_name}
                      </a>{' '}
                      <small>{attachment.size_bytes} bytes · SHA-256 {attachment.sha256.slice(0, 12)}…</small>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}

          {historyLoading && <Panel title="Seguimiento"><LoadingState rows={3} /></Panel>}
          {history && (
            <Panel title={`Seguimiento de ${history.documentNo}`} subtitle="Eventos documentales registrados" icon="history">
              {history.events.length === 0 ? (
                <EmptyState text="Sin eventos registrados." />
              ) : (
                <ol className="timeline">
                  {history.events.map((event, index) => (
                    <li key={index}>
                      <strong>{event.event_type.replaceAll('_', ' ')}</strong>
                      <span>{event.from_status ?? '—'} → {event.to_status ?? '—'}</span>
                      <small>
                        {formatDate(event.occurred_at)} · Actor {shortId(event.actor_id)}
                        {event.metadata ? ` · ${JSON.stringify(event.metadata).slice(0, 120)}` : ''}
                      </small>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
          )}

          {slaHistoryLoading && <Panel title="Historial SLA"><LoadingState rows={3} /></Panel>}
          {slaHistory && (
            <Panel
              title={`Historial SLA de ${slaHistory.documentNo}`}
              subtitle="Indicador calculado en backend; no sustituye al estado administrativo"
              icon="alert"
            >
              {slaHistory.events.length === 0 ? (
                <EmptyState text="Sin evaluaciones SLA registradas." />
              ) : (
                <ol className="timeline">
                  {slaHistory.events.map((event) => (
                    <li key={event.id}>
                      <SlaBadge sla={event} />
                      <span>{event.trigger.replaceAll('_', ' ')} · Ámbito {event.policy_scope}</span>
                      <small>
                        {formatDate(event.occurred_at)} · Transcurridas {formatNumber(event.elapsed_hours)} h ·
                        Actor {shortId(event.actor_id)}
                        {event.metadata_json
                          ? ` · Estado ${String(event.metadata_json.administrative_status ?? '—')}`
                          : ''}
                      </small>
                    </li>
                  ))}
                </ol>
              )}
            </Panel>
          )}

          {requisitions.length > 0 && (
            <Panel title="Control de cantidades por partida" subtitle="Solicitado, autorizado y surtido derivado de movimientos" icon="chart">
              <LineQuantitiesTable requisitions={requisitions} />
            </Panel>
          )}
        </>
      )}

      {pickerLine !== null && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal-card modal-wide" role="dialog" aria-modal="true" aria-labelledby="picker-title">
            <h3 id="picker-title">Seleccionar artículo · partida {pickerLine + 1}</h3>
            <p className="hint">Busque por código, descripción o número de parte. El catálogo no se modifica.</p>
            <ItemPicker
              selectedId={lines[pickerLine]?.item_id}
              warehouseId={warehouseId}
              onSelect={(item) => selectItem(pickerLine, item)}
            />
            <div className="form-actions">
              <button className="button button-secondary" type="button" onClick={() => setPickerLine(null)}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {confirm && (
        <ConfirmDialog
          title={confirm.title}
          message={confirm.message}
          confirmLabel={confirm.confirmLabel}
          needsReason={confirm.needsReason}
          reasonLabel={confirm.reasonLabel}
          onCancel={() => setConfirm(null)}
          onConfirm={(reason) => {
            const action = confirm.onConfirm;
            setConfirm(null);
            action(reason);
          }}
        />
      )}
    </>
  );
}
