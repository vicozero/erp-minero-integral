import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import type { Catalogs, PurchaseOrder, Requisition } from '../../api/types';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  PageHeader,
  Panel,
  StatusBadge,
  SuccessMessage,
} from '../../components/ui';

export function Purchases() {
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [requisitionId, setRequisitionId] = useState('');
  const [supplierId, setSupplierId] = useState('');
  const [warehouseId, setWarehouseId] = useState('');
  const [receiveLineId, setReceiveLineId] = useState('');
  const [receiveQty, setReceiveQty] = useState('1');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  const eligible = useMemo(
    () => requisitions.filter((req) => ['APPROVED', 'PARTIALLY_APPROVED'].includes(req.status)),
    [requisitions],
  );

  async function reload() {
    const [orderData, reqData, catalogData] = await Promise.all([
      api.purchases(),
      api.requisitions(),
      api.catalogs(),
    ]);
    setOrders(orderData);
    setRequisitions(reqData);
    setCatalogs(catalogData);
    setRequisitionId((current) => current || reqData.find((req) => eligible.some((e) => e.id === req.id))?.id || '');
    setSupplierId((current) => current || catalogData.suppliers[0]?.id || '');
    setWarehouseId((current) => current || catalogData.warehouses[0]?.id || '');
    setReceiveLineId((current) => current || orderData[0]?.lines[0]?.id || '');
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      setError(cause instanceof Error ? cause.message : 'Error al cargar.'),
    );
  }, []);

  async function createOrder() {
    if (sending) return;
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      const order = await api.createPurchase({
        requisition_id: requisitionId,
        supplier_id: supplierId,
        warehouse_id: warehouseId,
        notes: 'Generada desde la interfaz local',
        idempotency_key: `po:${requisitionId}:${supplierId}:${warehouseId}`,
      });
      setNotice(`Orden ${order.document_no} creada con ${order.lines.length} partidas.`);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible crear la orden.');
    } finally {
      setSending(false);
    }
  }

  async function approveOrder(id: string) {
    if (sending) return;
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      const order = await api.approvePurchase(id);
      setNotice(`Orden ${order.document_no} aprobada.`);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible aprobar.');
    } finally {
      setSending(false);
    }
  }

  async function cancelOrder(id: string) {
    if (sending) return;
    const reason = window.prompt('Motivo de la cancelación de la orden (mínimo 4 caracteres):');
    if (!reason) return;
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      await api.cancelPurchase(id, reason);
      setNotice('Orden cancelada. El faltante vuelve a estar disponible.');
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible cancelar la orden.');
    } finally {
      setSending(false);
    }
  }

  const orderForSelectedLine = orders.find((order) =>
    order.lines.some((line) => line.id === receiveLineId),
  );

  async function receiveOrder() {
    if (sending) return;
    if (!orderForSelectedLine) {
      setError('Seleccione una partida de orden válida.');
      return;
    }
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      const receipt = await api.receivePurchase(orderForSelectedLine.id, {
        lines: [{ purchase_order_line_id: receiveLineId, quantity: receiveQty }],
        // Clave estable por intención: un segundo clic sin cambios no genera
        // una segunda recepción ni una segunda entrada de inventario.
        idempotency_key: `grn:${receiveLineId}:${receiveQty}`,
      });
      setNotice(`Recepción ${receipt.document_no} registrada. Entrada de inventario generada.`);
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible recibir.');
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHeader title="Compras" subtitle="Órdenes por faltantes, aprobación y recepciones parciales" />
      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />

      <Panel title="Generar orden por faltantes">
        {catalogs && (
          <div className="grid-3">
            <label>Requisición autorizada
              <select value={requisitionId} onChange={(e) => setRequisitionId(e.target.value)}>
                {eligible.map((req) => <option key={req.id} value={req.id}>{req.document_no}</option>)}
              </select>
            </label>
            <label>Proveedor
              <select value={supplierId} onChange={(e) => setSupplierId(e.target.value)}>
                {catalogs.suppliers.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <label>Almacén de recepción
              <select value={warehouseId} onChange={(e) => setWarehouseId(e.target.value)}>
                {catalogs.warehouses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
            <button className="button button-primary align-end" type="button" disabled={sending} onClick={createOrder}>
              Generar orden
            </button>
          </div>
        )}
      </Panel>

      <Panel title="Recepción parcial">
        <div className="grid-3">
          <label>Partida de orden
            <select value={receiveLineId} onChange={(e) => setReceiveLineId(e.target.value)}>
              {orders.flatMap((order) =>
                order.lines.map((line) => (
                  <option key={line.id} value={line.id}>
                    {order.document_no} · partida {line.line_no} · pendiente {formatNumber(Number(line.ordered_qty) - Number(line.received_qty))}
                  </option>
                )),
              )}
            </select>
          </label>
          <label>Cantidad
            <input type="number" min="0.000001" step="any" value={receiveQty} onChange={(e) => setReceiveQty(e.target.value)} />
          </label>
          <div className="actions">
            {orderForSelectedLine && (
              <button className="button button-secondary" type="button" disabled={sending} onClick={receiveOrder}>
                Registrar recepción
              </button>
            )}
          </div>
        </div>
        <p className="hint">La recepción se asocia a la orden propietaria de la partida seleccionada.</p>
      </Panel>

      {orders.length === 0 ? (
        <EmptyState text="No hay órdenes de compra registradas." />
      ) : (
        orders.map((order) => (
          <Panel key={order.id} title={`${order.document_no} · ${order.status}`}>
            <table>
              <thead><tr><th>#</th><th>Artículo</th><th>Ordenada</th><th>Recibida</th><th>Precio</th></tr></thead>
              <tbody>
                {order.lines.map((line) => (
                  <tr key={line.id}>
                    <td>{line.line_no}</td>
                    <td>{line.item_id.slice(0, 8)}</td>
                    <td>{formatNumber(line.ordered_qty)}</td>
                    <td>{formatNumber(line.received_qty)}</td>
                    <td>{formatNumber(line.unit_price)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="form-actions">
              <StatusBadge status={order.status} />
              {order.status === 'DRAFT' && (
                <button
                  className="button button-primary button-small"
                  type="button"
                  disabled={sending}
                  onClick={() => approveOrder(order.id)}
                >
                  Aprobar orden
                </button>
              )}
              {['DRAFT', 'APPROVED', 'SENT'].includes(order.status) && (
                <button
                  className="button button-ghost button-small"
                  type="button"
                  disabled={sending}
                  onClick={() => cancelOrder(order.id)}
                >
                  Cancelar orden
                </button>
              )}
            </div>
          </Panel>
        ))
      )}
    </>
  );
}
