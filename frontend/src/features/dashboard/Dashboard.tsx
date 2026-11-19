import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, describeApiError } from '../../api/client';
import type { AuditEntry, Catalogs, PurchaseOrder, Requisition } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { can, PERM } from '../../auth/permissions';
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
  STATUS_LABELS,
  StatusBadge,
} from '../../components/ui';

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

function averageApprovalHours(requisitions: Requisition[]): number | null {
  const hours = requisitions
    .filter((req) => req.submitted_at && req.approved_at)
    .map((req) => (new Date(req.approved_at as string).getTime() - new Date(req.submitted_at as string).getTime()) / 3_600_000)
    .filter((value) => Number.isFinite(value) && value >= 0);
  if (hours.length === 0) return null;
  return hours.reduce((total, value) => total + value, 0) / hours.length;
}

export function Dashboard() {
  const { user } = useAuth();
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [orders, setOrders] = useState<PurchaseOrder[]>([]);
  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [audit, setAudit] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const canViewAudit = can(user, ...PERM.VIEW_AUDIT);

  async function load(): Promise<void> {
    setLoading(true);
    setError(null);
    const tasks: Array<Promise<unknown>> = [
      api.requisitions().then(setRequisitions),
      api.purchases().then(setOrders),
      api.catalogs().then(setCatalogs).catch(() => undefined),
    ];
    if (canViewAudit) {
      tasks.push(api.audit(8).then(setAudit).catch(() => setAudit([])));
    }
    const results = await Promise.allSettled(tasks);
    const failed: string[] = [];
    results.slice(0, 2).forEach((result, index) => {
      if (result.status === 'rejected') failed.push(index === 0 ? 'requisiciones' : 'compras');
    });
    if (failed.length > 0) setError(`No se pudieron cargar: ${failed.join(' y ')}. El resto de indicadores sí está disponible.`);
    setUpdatedAt(new Date());
    setLoading(false);
  }

  useEffect(() => {
    void load().catch((cause: unknown) => {
      setError(describeApiError(cause, 'No fue posible cargar el centro de operaciones.'));
      setLoading(false);
    });
    // La carga depende únicamente del permiso de auditoría del usuario activo.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canViewAudit]);

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

  const uomCode = (id: string): string => catalogs?.uoms.find((uom) => uom.id === id)?.code ?? id.slice(0, 8);

  const byUom = useMemo(() => {
    const lines = requisitions.flatMap((item) => item.lines);
    const groups = new Map<string, { requested: number; authorised: number; delivered: number; pending: number; lines: number }>();
    for (const line of lines) {
      const key = uomCode(line.uom_id);
      const group = groups.get(key) ?? { requested: 0, authorised: 0, delivered: 0, pending: 0, lines: 0 };
      group.requested += Number(line.requested_qty) || 0;
      group.authorised += Number(line.authorised_qty) || 0;
      group.delivered += Number(line.delivered_qty) || 0;
      group.pending += Number(line.pending_qty) || 0;
      group.lines += 1;
      groups.set(key, group);
    }
    return Array.from(groups.entries()).sort((a, b) => a[0].localeCompare(b[0]));
    // Las unidades se resuelven desde catálogos; recalcular cuando cambia.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requisitions, catalogs]);

  const pendingLines = requisitions.flatMap((req) => req.lines).filter((line) => (Number(line.pending_qty) || 0) > 0);
  const pendingOrders = orders.filter((order) => order.status === 'OPEN' || order.status === 'PARTIAL').length;
  const approvalHours = averageApprovalHours(requisitions);

  return (
    <>
      <PageHeader
        title="Centro de operaciones"
        subtitle="Indicadores calculados únicamente desde la API local del ERP"
        actions={
          <button className="button button-secondary" type="button" onClick={() => void load()} disabled={loading}>
            <Icon name="trend" size={14} /> {loading ? 'Actualizando…' : 'Actualizar datos'}
          </button>
        }
      />
      <DemoRibbon />
      <ErrorMessage message={error} />
      {updatedAt && (
        <p className="hint">Última lectura: {updatedAt.toLocaleString('es-MX')} · sin refresco automático.</p>
      )}

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
              <small>Documentos en el alcance del usuario</small>
            </Link>
            <Link className="metric-card tone-warning" to="/autorizaciones">
              <span><Icon name="clock" size={15} /> Autorizaciones pendientes</span>
              <strong>{reqCounts.SUBMITTED ?? 0}</strong>
              <small>Ir a la bandeja de autorizaciones</small>
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
            <div className="metric-card">
              <span><Icon name="box" size={15} /> Materiales pendientes</span>
              <strong>{pendingLines.length}</strong>
              <small>Partidas con saldo por entregar</small>
            </div>
            <div className="metric-card">
              <span><Icon name="history" size={15} /> Tiempo medio de autorización</span>
              <strong>{approvalHours === null ? 'N/D' : `${approvalHours.toFixed(1)} h`}</strong>
              <small>
                {approvalHours === null
                  ? 'No disponible: aún no hay documentos autorizados con fecha de envío'
                  : 'Desde enviado hasta autorizado'}
              </small>
            </div>
          </div>

          <div className="panel-grid">
            <Panel title="Solicitudes por estado" subtitle="Distribución del circuito de requisiciones" icon="chart">
              <StatusChart counts={reqCounts} total={requisitions.length} />
            </Panel>
            <Panel title="Órdenes de compra por estado" subtitle="Seguimiento de compromisos" icon="truck">
              <StatusChart counts={orderCounts} total={orders.length} />
            </Panel>
          </div>

          <Panel
            title="Cumplimiento de surtido por unidad"
            subtitle="Cada unidad se mantiene separada para no mezclar kilogramos, litros o piezas"
            icon="trend"
          >
            {byUom.length === 0 ? (
              <EmptyState text="No hay partidas registradas." />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Unidad</th><th>Partidas</th><th>Solicitado</th><th>Autorizado</th><th>Entregado</th><th>Pendiente</th><th>Surtido</th></tr>
                  </thead>
                  <tbody>
                    {byUom.map(([uom, values]) => (
                      <tr key={uom}>
                        <td><strong>{uom}</strong></td>
                        <td>{values.lines}</td>
                        <td>{formatNumber(values.requested)}</td>
                        <td>{formatNumber(values.authorised)}</td>
                        <td>{formatNumber(values.delivered)}</td>
                        <td>{formatNumber(values.pending)}</td>
                        <td className="progress-cell">
                          <ProgressBar
                            value={values.delivered}
                            max={values.authorised}
                            tone={values.authorised > 0 && values.delivered >= values.authorised ? 'success' : 'default'}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel title="Indicadores no disponibles con la API actual" subtitle="Se muestran explícitamente para no inventar valores" icon="alert">
            <ul className="unavailable-list">
              <li><strong>Monto autorizado y valuación:</strong> las líneas de requisición no exponen importes ni costo enlazado.</li>
              <li><strong>Cumplimiento de SLA:</strong> no existe una política de plazos aprobada en el backend.</li>
              <li><strong>Existencias globales y rupturas:</strong> solo hay disponibilidad por artículo y almacén, sin agregado.</li>
              <li><strong>Solicitante por documento:</strong> el contrato de requisición no expone al solicitante.</li>
            </ul>
          </Panel>

          <Panel title="Actividad reciente" subtitle="Últimos 8 documentos y eventos de auditoría disponibles" icon="history">
            <h3>Últimas requisiciones</h3>
            {requisitions.length === 0 ? (
              <EmptyState text="Aún no hay requisiciones registradas." />
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr><th>Folio</th><th>Prioridad</th><th>Partidas</th><th>Estado</th><th>Fecha</th></tr>
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
            <h3>Bitácora reciente</h3>
            {canViewAudit ? (
              audit.length === 0 ? (
                <EmptyState text="Sin entradas de auditoría disponibles para el usuario." />
              ) : (
                <ol className="timeline compact">
                  {audit.map((entry) => (
                    <li key={entry.id}>
                      <strong>{entry.action}</strong>
                      <span>{entry.entity_type} · {entry.entity_id?.slice(0, 8) ?? 'sistema'}</span>
                      <small>{new Date(entry.occurred_at).toLocaleString('es-MX')} · {entry.actor_username ?? 'sistema'}</small>
                    </li>
                  ))}
                </ol>
              )
            ) : (
              <EmptyState text="La bitácora requiere el permiso auditoria.consultar." />
            )}
          </Panel>
        </>
      )}
    </>
  );
}
