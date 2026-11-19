import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import type { Requisition, RequisitionLine } from '../../api/types';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  PageHeader,
  Panel,
  SuccessMessage,
} from '../../components/ui';

interface LineChoice {
  selected: boolean;
  quantity: string;
  reason: string;
}

type ChoiceMap = Record<string, LineChoice>;
type DecisionMode = 'APPROVE_SELECTED' | 'REJECT_SELECTED' | 'APPROVE_ALL' | 'REJECT_ALL';

function defaultChoices(lines: RequisitionLine[]): ChoiceMap {
  return Object.fromEntries(
    lines.map((line) => [
      line.id,
      { selected: true, quantity: line.requested_qty, reason: '' } satisfies LineChoice,
    ]),
  );
}

export function Approvals() {
  const [pending, setPending] = useState<Requisition[]>([]);
  const [choices, setChoices] = useState<Record<string, ChoiceMap>>({});
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function reload() {
    const all = await api.requisitions();
    const submitted = all.filter((req) => req.status === 'SUBMITTED');
    setPending(submitted);
    setChoices(Object.fromEntries(submitted.map((req) => [req.id, defaultChoices(req.lines)])));
  }

  useEffect(() => {
    reload().catch((cause: unknown) =>
      setError(cause instanceof Error ? cause.message : 'Error al cargar.'),
    );
  }, []);

  function updateChoice(requisitionId: string, lineId: string, patch: Partial<LineChoice>): void {
    setChoices((current) => ({
      ...current,
      [requisitionId]: {
        ...(current[requisitionId] ?? {}),
        [lineId]: {
          ...(current[requisitionId]?.[lineId] ?? {
            selected: true,
            quantity: '0',
            reason: '',
          }),
          ...patch,
        },
      },
    }));
  }

  async function decide(req: Requisition, mode: DecisionMode) {
    setError(null);
    setNotice(null);
    const current = choices[req.id] ?? defaultChoices(req.lines);
    const rejectSelected = mode === 'REJECT_SELECTED';
    const rejectAll = mode === 'REJECT_ALL';
    const approveAll = mode === 'APPROVE_ALL';
    const rejectMode = rejectSelected || rejectAll;

    const decisions = req.lines.map((line) => {
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

    const invalidLine = req.lines.find((line) => {
      const choice = current[line.id];
      if (!choice || !choice.selected || rejectMode) return false;
      const qty = Number(choice.quantity);
      return !Number.isFinite(qty) || qty < 0 || qty > Number(line.requested_qty);
    });
    if (invalidLine) {
      setError(`Revise la cantidad autorizada de la partida ${invalidLine.line_no}.`);
      return;
    }
    if (decisions.some((item) => item.decision === 'REJECT' && !item.reason)) {
      setError('Indique un motivo general o un motivo por partida para los rechazos.');
      return;
    }

    try {
      const result = await api.decideRequisition(req.id, decisions, reason || undefined);
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
        <p className="hint">
          Seleccione las partidas a autorizar. Las no seleccionadas se dejan en cero con motivo, sin
          omitirlas de la decisión.
        </p>
        <label>
          Motivo general (obligatorio en rechazos)
          <input value={reason} onChange={(event) => setReason(event.target.value)} />
        </label>
      </Panel>
      {pending.length === 0 ? (
        <EmptyState text="No hay requisiciones pendientes de autorización." />
      ) : (
        pending.map((req) => (
          <Panel key={req.id} title={`${req.document_no} · ${req.priority}`}>
            <p>{req.justification}</p>
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
                    const choice = choices[req.id]?.[line.id] ?? {
                      selected: true,
                      quantity: line.requested_qty,
                      reason: '',
                    };
                    return (
                      <tr key={line.id}>
                        <td>
                          <input
                            type="checkbox"
                            aria-label={`Incluir partida ${line.line_no}`}
                            checked={choice.selected}
                            onChange={(event) =>
                              updateChoice(req.id, line.id, { selected: event.target.checked })
                            }
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
                            onChange={(event) =>
                              updateChoice(req.id, line.id, { quantity: event.target.value })
                            }
                          />
                        </td>
                        <td>
                          <input
                            aria-label={`Motivo de la partida ${line.line_no}`}
                            value={choice.reason}
                            onChange={(event) =>
                              updateChoice(req.id, line.id, { reason: event.target.value })
                            }
                          />
                        </td>
                        <td>{line.uom_id.slice(0, 8)}</td>
                        <td>{line.notes ?? '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="form-actions">
              <button
                className="button button-primary"
                type="button"
                onClick={() => decide(req, 'APPROVE_SELECTED')}
              >
                Autorizar seleccionadas
              </button>
              <button
                className="button button-secondary"
                type="button"
                onClick={() => decide(req, 'APPROVE_ALL')}
              >
                Autorizar todo
              </button>
              <button
                className="button button-danger"
                type="button"
                onClick={() => decide(req, 'REJECT_SELECTED')}
              >
                Rechazar seleccionadas
              </button>
              <button
                className="button button-danger"
                type="button"
                onClick={() => decide(req, 'REJECT_ALL')}
              >
                Rechazar todo
              </button>
            </div>
          </Panel>
        ))
      )}
    </>
  );
}
