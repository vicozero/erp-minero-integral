import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { PurchaseOrder, Requisition } from '../../api/types';
import { Icon } from '../../components/Icon';
import {
  DemoRibbon,
  EmptyState,
  ErrorMessage,
  formatNumber,
  LoadingState,
  PageHeader,
  Panel,
  ProgressBar,
  StatusBadge,
} from '../../components/ui';

const STATUS_LABELS: Record<string, string> = {
  DRAFT: 'Borrador',
  SUBMITTED: 'Enviada',
  APPROVED: 'Autorizada',
  PARTIALLY_APPROVED: 'Parcial',
  REJECTED: 'Rechazada',
  CANCELLED: 'Cancelada',
  OPEN: 'Abierta',
  PARTIAL: 'Parcial',
  RECEIVED: 'Recibida',
  PARTIALLY_RECEIVED: 'Recibida parcial',
};

const STATUS_TONE: Record<string, string> = {
  SUBMITTED: 'amber',
  PENDING: 'amber',
  OPEN: 'amber',
  REJECTED: 'red',
  CANCELLED: 'red',
  APPROVED: 'green',
  RECEIVED: 'green',
  COMPLETED: 'green',
};

function StatusChart({ counts, total }: { counts: Record<string, number>; total: number }) {
  const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) return <EmptyState text="Sin estados registrados." />;
  return (
    <div className="chart">
      {entries.map(([status, value]) => (
        <div className="chart-row" key={status}>
          <span>{STATUS_LABELS[status] ?? status.replaceAll('_', ' ')}</span>
          <div className={`chart-bar ${STATUS_TONE[status] ?? ''}`}>
            <i style={{ width: `${total > 0 ? (value / total) * 100 : 0}%` }} />
          </div>
          <strong>{value}</strong>
        </div>
      ))}
    </div>
  );
}

export function Dashboard() {
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.allSettled([api.requisitions(), api.purchases()]).then(([reqResult, orderResult]) => {
      if (!active) return;
      const failed: string[] = [];
      if (reqResult.status === 'fulfilled') setRequisitions(reqResult.value);
      else failed.push('requisiciones');
      if (orderResult.status === 'fulfilled') setOrders(orderResult.value);
      else failed.push('compras');
      if (failed.length > 0) setError(`No se pudieron cargar: ${failed.join(' y ')}.`);
      setLoading(false);
    });
    return () => { active = false; };
  }, []);

  const reqCounts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const item of requisitions) result[item.status] = (result[item.status] ?? 0) + 1;
    return result;
  }, [requisitions]);

  const orderCounts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const item of orders) result[item.status] = (result[item.status] ?? 0) + 1;
    return result;
  }, [orders]);

  const flow = useMemo(() => {
    const lines = requisitions.flatMap((item) => item.lines);
    const sum = (pick: (line: (typeof lines)[number]) => string): number =>
      lines.reduce((total, line) => total + (Number(pick(line)) || 0), 0);
    return {
      requested: sum((line) => line.requested_qty),
      authorised: sum((line) => line.authorised_qty),
      reserved: sum((line) => line.reserved_qty),
      purchased: sum((line) => line.purchased_qty),
      received: sum((line) => line.received_qty),
      delivered: sum((line) => line.delivered_qty),
    };
  }, [requisitions]);

  const pendingOrders = orders.filter((order) => order.status === 'OPEN' || order.status === 'PARTIAL').length;

  return (
    <>
      <PageHeader
        title="Centro de operaciones"
        subtitle="Resumen ejecutivo del circuito de requisiciones, almacén y compras"
        actions={
          <span className="badge badge-active">
            <Icon name="trend" size={13} /> Indicadores en vivo
          </span>
        }
      />
      <DemoRibbon />

      <ErrorMessage message={error} />

      {loading ? (
        <Panel title="Cargando indicadores" icon="chart">
          <LoadingState rows={5} />
        </Panel>
      ) : (
        <>
          <div className="card-grid">
            <Link className="metric-card" to="/requisiciones">
              <span><Icon name="requisitions" size={15} /> Requisiciones</span>
              <strong>{requisitions.length}</strong>
              <small>Documentos registrados</small>
            </Link>
            <Link className="metric-card tone-warning" to="/autorizaciones">
              <span><Icon name="clock" size={15} /> Pendientes de autorizar</span>
              <strong>{reqCounts.SUBMITTED ?? 0}</strong>
              <small>Ir a autorizaciones</small>
            </Link>
            <Link className="metric-card tone-success" to="/almacen">
              <span><Icon name="check" size={15} /> Autorizadas</span>
              <strong>{(reqCounts.APPROVED ?? 0) + (reqCounts.PARTIALLY_APPROVED ?? 0)}</strong>
              <small>Listas para surtir</small>
            </Link>
            <Link className="metric-card tone-info" to="/compras">
              <span><Icon name="purchases" size={15} /> Órdenes de compra</span>
              <strong>{orders.length}</strong>
              <small>{pendingOrders} abiertas o parciales</small>
            </Link>
          </div>

          <div className="panel-grid">
            <Panel title="Requisiciones por estado" subtitle="Distribución del circuito de autorización" icon="chart">
              <StatusChart counts={reqCounts} total={requisitions.length} />
            </Panel>
            <Panel title="Órdenes de compra por estado" subtitle="Seguimiento de compromisos" icon="truck">
              <StatusChart counts={orderCounts} total={orders.length} />
            </Panel>
          </div>

          <Panel title="Flujo de suministro por partida" subtitle="Cantidades acumuladas desde las líneas de requisición" icon="trend">
            <div className="detail-grid">
              <div>
                <span>Solicitado</span>
                <strong>{formatNumber(flow.requested)}</strong>
              </div>
              <div>
                <span>Autorizado</span>
                <strong>{formatNumber(flow.authorised)}</strong>
              </div>
              <div>
                <span>Reservado</span>
                <strong>{formatNumber(flow.reserved)}</strong>
              </div>
              <div>
                <span>Comprado</span>
                <strong>{formatNumber(flow.purchased)}</strong>
              </div>
              <div>
                <span>Recibido</span>
                <strong>{formatNumber(flow.received)}</strong>
              </div>
              <div>
                <span>Surtido</span>
                <strong>{formatNumber(flow.delivered)}</strong>
              </div>
            </div>
            <div style={{ display: 'grid', gap: 12, marginTop: 18 }}>
              <ProgressBar value={flow.authorised} max={flow.requested} label="Autorizado / solicitado" />
              <ProgressBar value={flow.delivered} max={flow.requested} tone="success" label="Surtido / solicitado" />
              <ProgressBar value={flow.received} max={flow.purchased} tone="warning" label="Recibido / comprado" />
            </div>
          </Panel>

          <Panel title="Últimas requisiciones" subtitle="Los 8 documentos más recientes" icon="requisitions">
            {requisitions.length === 0 ? (
              <EmptyState text="Aún no hay requisiciones registradas." />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Folio</th>
                      <th>Prioridad</th>
                      <th>Partidas</th>
                      <th>Estado</th>
                      <th>Fecha</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requisitions.slice(0, 8).map((req) => (
                      <tr key={req.id}>
                        <td>{req.document_no}</td>
                        <td>{req.priority}</td>
                        <td>{req.lines.length}</td>
                        <td><StatusBadge status={req.status} /></td>
                        <td>{new Date(req.created_at).toLocaleString('es-MX')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </>
      )}
    </>
  );
}
