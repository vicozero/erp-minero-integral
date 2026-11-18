import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../../api/client';
import type { Requisition } from '../../api/types';
import { EmptyState, ErrorMessage, PageHeader, StatusBadge } from '../../components/ui';

export function Dashboard() {
  const [requisitions, setRequisitions] = useState<Requisition[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.requisitions()
      .then(setRequisitions)
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : 'Error al cargar.'));
  }, []);

  const counts = useMemo(() => {
    const result: Record<string, number> = {};
    for (const req of requisitions) {
      result[req.status] = (result[req.status] ?? 0) + 1;
    }
    return result;
  }, [requisitions]);

  return (
    <>
      <PageHeader
        title="Dashboard general"
        subtitle="Resumen operativo del circuito de requisiciones"
      />
      <ErrorMessage message={error} />
      <div className="card-grid">
        <Link className="metric-card" to="/requisiciones">
          <span>Requisiciones</span>
          <strong>{requisitions.length}</strong>
          <small>Ver detalle</small>
        </Link>
        <Link className="metric-card" to="/autorizaciones">
          <span>Pendientes de autorizar</span>
          <strong>{counts.SUBMITTED ?? 0}</strong>
          <small>Ir a autorizaciones</small>
        </Link>
        <Link className="metric-card" to="/almacen">
          <span>Autorizadas</span>
          <strong>{(counts.APPROVED ?? 0) + (counts.PARTIALLY_APPROVED ?? 0)}</strong>
          <small>Ir a almacén</small>
        </Link>
        <Link className="metric-card" to="/compras">
          <span>Órdenes de compra</span>
          <strong>—</strong>
          <small>Ir a compras</small>
        </Link>
      </div>

      <section className="panel">
        <h2>Últimas requisiciones</h2>
        {requisitions.length === 0 ? (
          <EmptyState text="Aún no hay requisiciones registradas." />
        ) : (
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
        )}
      </section>
    </>
  );
}
