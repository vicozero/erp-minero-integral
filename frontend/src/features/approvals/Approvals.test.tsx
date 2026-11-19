import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { Requisition } from '../../api/types';
import { Approvals } from './Approvals';

function line(id: string, lineNo: number, qty: string) {
  return {
    id,
    line_no: lineNo,
    item_id: null,
    description: `Artículo ${lineNo}`,
    uom_id: '11111111-1111-1111-1111-111111111111',
    requested_qty: qty,
    authorised_qty: '0',
    cancelled_qty: '0',
    status: 'PENDING',
    notes: null,
    reserved_qty: '0',
    purchased_qty: '0',
    received_qty: '0',
    delivered_qty: '0',
    pending_qty: qty,
  };
}

function requisition(): Requisition {
  return {
    id: 'req-1',
    document_no: 'REQ-LAG-2026-000001',
    department_id: 'dep-1',
    warehouse_id: null,
    equipment_id: null,
    cost_center_id: 'cost-1',
    requisition_type: 'STOCK',
    priority: 'NORMAL',
    status: 'SUBMITTED',
    justification: 'Prueba de autorización parcial',
    observations: null,
    needed_at: null,
    submitted_at: null,
    approved_at: null,
    rejected_at: null,
    rejection_reason: null,
    work_order_no: null,
    created_at: '2026-11-18T10:00:00Z',
    lines: [line('line-1', 1, '10'), line('line-2', 2, '5')],
  };
}

function mockApi(resultStatus = 'PARTIALLY_APPROVED') {
  const req = requisition();
  const list = vi.spyOn(api, 'requisitions').mockResolvedValue([req]);
  const decide = vi
    .spyOn(api, 'decideRequisition')
    .mockResolvedValue({ ...req, status: resultStatus });
  return { decide, list };
}

describe('Autorización parcial por partida', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('envía la cantidad editada y deja en cero la partida no seleccionada', async () => {
    const { decide } = mockApi();
    render(<Approvals />);

    await screen.findByRole('heading', { name: /REQ-LAG-2026-000001/ });
    fireEvent.click(screen.getByLabelText('Incluir partida 2'));
    fireEvent.change(screen.getByLabelText('Cantidad a autorizar de la partida 1'), {
      target: { value: '7.5' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Autorizar seleccionadas' }));

    await waitFor(() => expect(decide).toHaveBeenCalledTimes(1));
    const [, decisions] = decide.mock.calls[0];
    expect(decisions).toEqual([
      expect.objectContaining({
        requisition_line_id: 'line-1',
        decision: 'APPROVE',
        approved_qty: '7.5',
      }),
      expect.objectContaining({
        requisition_line_id: 'line-2',
        decision: 'APPROVE',
        approved_qty: '0',
      }),
    ]);
  });

  it('al rechazar una partida conserva autorizadas las demás', async () => {
    const { decide } = mockApi('REJECTED');
    render(<Approvals />);

    await screen.findByRole('heading', { name: /REQ-LAG-2026-000001/ });
    fireEvent.click(screen.getByLabelText('Incluir partida 1'));
    fireEvent.change(screen.getByLabelText('Motivo general (obligatorio en rechazos)'), {
      target: { value: 'Falta de presupuesto' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Rechazar seleccionadas' }));

    await waitFor(() => expect(decide).toHaveBeenCalledTimes(1));
    const [, decisions] = decide.mock.calls[0];
    expect(decisions).toEqual([
      expect.objectContaining({
        requisition_line_id: 'line-1',
        decision: 'APPROVE',
        approved_qty: '10',
      }),
      expect.objectContaining({
        requisition_line_id: 'line-2',
        decision: 'REJECT',
        approved_qty: '0',
        reason: 'Falta de presupuesto',
      }),
    ]);
  });
});
