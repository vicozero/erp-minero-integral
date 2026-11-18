import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import type { Availability, Catalogs, Requisition, StockMovement } from '../../api/types';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  PageHeader,
  Panel,
  SuccessMessage,
} from '../../components/ui';

function newKey(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export function Inventory() {
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [kardex, setKardex] = useState<StockMovement[]>([]);
  const [itemId, setItemId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [lineId, setLineId] = useState('');
  const [quantity, setQuantity] = useState('1');
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const lines = useMemo(
    () =>
      requisitions
        .filter((req) => ['APPROVED', 'PARTIALLY_APPROVED', 'IN_PROGRESS'].includes(req.status))
        .flatMap((req) => req.lines.map((line) => ({ req, line })))
        .filter(({ line }) => Number(line.authorised_qty) > Number(line.delivered_qty)),
    [requisitions],
  );

  async function reload() {
    const [catalogData, reqData, movements] = await Promise.all([
      api.catalogs(),
      api.requisitions(),
      api.kardex(),
    ]);
    setCatalogs(catalogData);
    setRequisitions(reqData);
    setKardex(movements);
    setItemId((current) => current || catalogData.items[0]?.id || '');
    setWarehouseId((current) => current || catalogData.warehouses[0]?.id || '');
    setLineId((current) => current || lines[0]?.line.id || '');
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      setError(cause instanceof Error ? cause.message : 'Error al cargar.'),
    );
  }, []);

  async function checkAvailability() {
    setError(null);
    try {
      setAvailability(await api.availability(itemId, warehouseId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Error al consultar existencia.');
    }
  }

  async function action(kind: 'reserve' | 'issue') {
    setError(null);
    setNotice(null);
    try {
      if (kind === 'reserve') {
        await api.reserve({
          requisition_line_id: lineId,
          quantity,
          idempotency_key: newKey('res'),
        });
        setNotice('Reserva registrada. La existencia no se ha descontado.');
      } else {
        const movement = await api.issue({
          requisition_line_id: lineId,
          quantity,
          idempotency_key: newKey('iss'),
        });
        setNotice(`Entrega ${movement.movement_no} registrada y descontada del inventario.`);
      }
      await reload();
      await checkAvailability();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible completar la operación.');
    }
  }

  return (
    <>
      <PageHeader title="Almacén" subtitle="Disponibilidad, reservas, entregas y kardex" />
      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />

      <Panel title="Consultar disponibilidad">
        {catalogs && (
          <div className="grid-3">
            <label>Artículo
              <select value={itemId} onChange={(event) => setItemId(event.target.value)}>
                {catalogs.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label>Almacén
              <select value={warehouseId} onChange={(event) => setWarehouseId(event.target.value)}>
                {catalogs.warehouses.map((warehouse) => (
                  <option key={warehouse.id} value={warehouse.id}>{warehouse.name}</option>
                ))}
              </select>
            </label>
            <button className="button button-secondary align-end" type="button" onClick={checkAvailability}>
              Consultar
            </button>
          </div>
        )}
        {availability && (
          <div className="availability-grid">
            <div><span>Existencia</span><strong>{formatNumber(availability.on_hand_qty)}</strong></div>
            <div><span>Reservado</span><strong>{formatNumber(availability.reserved_qty)}</strong></div>
            <div><span>Disponible</span><strong>{formatNumber(availability.available_qty)}</strong></div>
          </div>
        )}
      </Panel>

      <Panel title="Reservar y entregar">
        {lines.length === 0 ? (
          <EmptyState text="No hay partidas autorizadas pendientes de entrega." />
        ) : (
          <div className="grid-3">
            <label>Partida
              <select value={lineId} onChange={(event) => setLineId(event.target.value)}>
                {lines.map(({ req, line }) => (
                  <option key={line.id} value={line.id}>
                    {req.document_no} · {line.description} · pendiente {formatNumber(line.pending_qty)}
                  </option>
                ))}
              </select>
            </label>
            <label>Cantidad
              <input type="number" min="0.000001" step="any" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </label>
            <div className="actions">
              <button className="button button-secondary" type="button" onClick={() => action('reserve')}>Reservar</button>
              <button className="button button-primary" type="button" onClick={() => action('issue')}>Entregar</button>
            </div>
          </div>
        )}
      </Panel>

      <Panel title="Kardex transaccional">
        {kardex.length === 0 ? (
          <EmptyState text="No hay movimientos registrados." />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Movimiento</th><th>Tipo</th><th>Dirección</th><th>Cantidad</th><th>Saldo posterior</th><th>Fecha</th></tr>
              </thead>
              <tbody>
                {kardex.slice(0, 30).map((movement) => (
                  <tr key={movement.id}>
                    <td>{movement.movement_no}</td>
                    <td>{movement.movement_type}</td>
                    <td>{movement.direction}</td>
                    <td>{formatNumber(movement.quantity)}</td>
                    <td>{formatNumber(movement.balance_after_qty)}</td>
                    <td>{new Date(movement.posted_at).toLocaleString('es-MX')}</td>
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
