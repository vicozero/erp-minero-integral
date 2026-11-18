import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { Requisition } from '../../api/types';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  PageHeader,
  Panel,
  SuccessMessage,
} from '../../components/ui';

export function Approvals() {
  const [pending, setPending] = useState<Requisition[]>([]);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function reload() {
    const all = await api.requisitions();
    setPending(all.filter((req) => req.status === 'SUBMITTED'));
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      setError(cause instanceof Error ? cause.message : 'Error al cargar.'),
    );
  }, []);

  async function decide(req: Requisition, decision: 'APPROVE' | 'REJECT') {
    setError(null);
    setNotice(null);
    try {
      const result = await api.decideRequisition(
        req.id,
        req.lines.map((line) => ({
          requisition_line_id: line.id,
          decision,
          approved_qty: decision === 'APPROVE' ? line.requested_qty : '0',
        })),
        reason || undefined,
      );
      setNotice(`${req.document_no}: ${result.status.replaceAll('_', ' ')}.`);
      setReason('');
      await reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'No fue posible registrar la decisión.');
    }
  }

  return (
    <>
      <PageHeader title="Autorizaciones" subtitle="Revisión y decisión de requisiciones enviadas" />
      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />
      <Panel title="Cantidades a autorizar">
        <label>Motivo general (obligatorio en rechazos)
          <input value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
      </Panel>
      {pending.length === 0 ? (
        <EmptyState text="No hay requisiciones pendientes de autorización." />
      ) : (
        pending.map((req) => (
          <Panel key={req.id} title={`${req.document_no} · ${req.priority}`}>
            <p>{req.justification}</p>
            <table>
              <thead>
                <tr><th>#</th><th>Artículo</th><th>Solicitada</th><th>UOM</th><th>Notas</th></tr>
              </thead>
              <tbody>
                {req.lines.map((line) => (
                  <tr key={line.id}>
                    <td>{line.line_no}</td>
                    <td>{line.description}</td>
                    <td>{formatNumber(line.requested_qty)}</td>
                    <td>{line.uom_id.slice(0, 8)}</td>
                    <td>{line.notes ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="form-actions">
              <button className="button button-primary" type="button" onClick={() => decide(req, 'APPROVE')}>
                Autorizar todo
              </button>
              <button className="button button-danger" type="button" onClick={() => decide(req, 'REJECT')}>
                Rechazar
              </button>
            </div>
          </Panel>
        ))
      )}
    </>
  );
}
