import { useEffect, useState, type FormEvent } from 'react';
import { api } from '../../api/client';
import type { Catalogs, HistoryEvent, Requisition, RequisitionPayload } from '../../api/types';
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
  const [history, setHistory] = useState<{ id: string; events: HistoryEvent[] } | null>(null);

  const [departmentId, setDepartmentId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [costCenterId, setCostCenterId] = useState('');
  const [priority, setPriority] = useState<RequisitionPayload['priority']>('NORMAL');
  const [justification, setJustification] = useState('');
  const [observations, setObservations] = useState('');
  const [lines, setLines] = useState<DraftLine[]>([]);

  async function reload() {
    setRequisitions(await api.requisitions());
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
    setError(null);
    setNotice(null);
    try {
      const payload: RequisitionPayload = {
        department_id: departmentId,
        warehouse_id: warehouseId || null,
        equipment_id: equipmentId || null,
        cost_center_id: costCenterId,
        requisition_type: 'STOCK',
        priority,
        justification,
        observations: observations || null,
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
      if (catalogs) setLines([emptyLine(catalogs)]);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible guardar.');
    }
  }

  async function handleSubmit(id: string) {
    setError(null);
    setNotice(null);
    try {
      const updated = await api.submitRequisition(id);
      setNotice(`${updated.document_no} enviada a autorización.`);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible enviar.');
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

  return (
    <>
      <PageHeader
        title="Requisiciones"
        subtitle="Captura, envío y seguimiento por partida"
      />
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
              <label>Prioridad
                <select value={priority} onChange={(e) => setPriority(e.target.value as RequisitionPayload['priority'])}>
                  {['LOW', 'NORMAL', 'HIGH', 'URGENT'].map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
            </div>
            <label>Justificación
              <textarea value={justification} onChange={(e) => setJustification(e.target.value)} required minLength={4} />
            </label>
            <label>Observaciones
              <input value={observations} onChange={(e) => setObservations(e.target.value)} />
            </label>

            <h3>Partidas</h3>
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
                <label>Unidad
                  <select value={line.uom_id} onChange={(e) => updateLine(index, { uom_id: e.target.value })}>
                    {catalogs.uoms.map((uom) => <option key={uom.id} value={uom.id}>{uom.code}</option>)}
                  </select>
                </label>
                <label>Cantidad
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
              <button className="button button-secondary" type="submit">Guardar borrador</button>
              <button className="button button-primary" type="button" onClick={(event) => handleCreate(event, true)}>
                Guardar y enviar
              </button>
            </div>
          </form>
        </Panel>
      )}

      <Panel title="Listado de requisiciones">
        {requisitions.length === 0 ? (
          <EmptyState text="No hay requisiciones registradas." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Folio</th>
                  <th>Estado</th>
                  <th>Partidas</th>
                  <th>Justificación</th>
                  <th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {requisitions.map((req) => (
                  <tr key={req.id}>
                    <td>{req.document_no}</td>
                    <td><StatusBadge status={req.status} /></td>
                    <td>{req.lines.length}</td>
                    <td>{req.justification}</td>
                    <td className="actions">
                      {req.status === 'DRAFT' && (
                        <button className="button button-small" type="button" onClick={() => handleSubmit(req.id)}>
                          Enviar
                        </button>
                      )}
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

      {history && (
        <Panel title={`Seguimiento de requisición ${history.id.slice(0, 8)}`}>
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
