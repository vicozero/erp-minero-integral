import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { api } from '../../api/client';
import type { RequisitionTrace, User } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { Traceability } from './Traceability';

const user: User = {
  id: 'user-1',
  username: 'demo.admin',
  email: 'admin.demo@example.invalid',
  full_name: 'Administrador Demo',
  status: 'ACTIVE',
  roles: ['ADMIN'],
  permissions: ['requisition.history.view'],
  department_ids: [],
  must_change_password: false,
};

const trace: RequisitionTrace = {
  requisition_id: 'req-1',
  document_no: 'REQ-LAG-2026-000001',
  administrative_status: 'APPROVED',
  tracking: {
    sla: {
      color: 'GREEN',
      label: 'En plazo',
      measured: true,
      administrative_status: 'APPROVED',
      base_at: '2026-11-19T09:00:00Z',
      elapsed_hours: '2.00',
      green_deadline: '2026-11-20T09:00:00Z',
      yellow_deadline: '2026-11-21T09:00:00Z',
      policy_id: 'policy-1',
      policy_scope: 'GLOBAL/LOW',
      emergency_active: false,
      message: null,
    },
    administrative_status: 'APPROVED',
    pending_days: '1.00',
    fulfillment_percent: '100.00',
    needed_at: '2026-11-20T09:00:00Z',
  },
  stages: [
    { stage: 'REQUISICION', label: 'Requisición', completed: true, document_no: 'REQ-LAG-2026-000001', occurred_at: '2026-11-19T09:00:00Z', detail: 'APPROVED' },
    { stage: 'AUTORIZACION', label: 'Autorización', completed: true, document_no: 'REQ-LAG-2026-000001', occurred_at: '2026-11-19T09:30:00Z', detail: '1 decisión' },
    { stage: 'RESERVA', label: 'Reserva', completed: true, document_no: null, occurred_at: '2026-11-19T10:00:00Z', detail: '1 reserva' },
    { stage: 'ENTREGA', label: 'Entrega', completed: true, document_no: null, occurred_at: '2026-11-19T11:00:00Z', detail: '1 movimiento' },
    { stage: 'VALE', label: 'Vale de almacén', completed: true, document_no: 'VA-000166', occurred_at: '2026-11-19T11:30:00Z', detail: '1 vale' },
    { stage: 'SEGUIMIENTO', label: 'Seguimiento SLA', completed: true, document_no: 'REQ-LAG-2026-000001', occurred_at: '2026-11-19T09:00:00Z', detail: 'En plazo · surtido 100.00%' },
  ],
  approvals: [{ id: 'dec-1', decision: 'APPROVE', decided_by: 'Aprobador Demo', decided_at: '2026-11-19T09:30:00Z' }],
  reservations: [{ id: 'res-1', reservation_no: 'RES-000001', quantity: '2', status: 'ACTIVE' }],
  deliveries: [{ id: 'mov-1', movement_no: 'MOV-000001', quantity: '2', posted_at: '2026-11-19T11:00:00Z' }],
  vouchers: [{
    id: 'va-1',
    document_no: 'VA-000166',
    status: 'ISSUED',
    received_by_name: 'RECEPCION SINTETICA',
    authorized_by_name: 'AUTORIZACION SINTETICA',
    dispatched_by_name: 'DESPACHO SINTETICO',
    renders: [{ id: 'render-1', document_format: 'PDF', is_reprint: false, sha256: 'a'.repeat(64), rendered_at: '2026-11-19T11:31:00Z' }],
  }],
  document_events: [{ event_type: 'VOUCHER_CREATED', from_status: null, to_status: 'DRAFT', occurred_at: '2026-11-19T11:30:00Z' }],
  audit_events: [{ action: 'VOUCHER_CREATE', entity_type: 'WarehouseVoucher', actor_username: 'demo.almacenista', occurred_at: '2026-11-19T11:30:00Z', request_id: 'req-id-1' }],
  generated_at: '2026-11-19T12:00:00Z',
};

function renderTrace(requisitionId = 'req-1') {
  vi.spyOn(api, 'requisitionTrace').mockResolvedValue(trace);
  render(
    <MemoryRouter initialEntries={[`/trazabilidad/${requisitionId}`]}>
      <Routes>
        <Route
          path="/trazabilidad/:requisitionId"
          element={<AuthProvider initialUser={user}><Traceability /></AuthProvider>}
        />
      </Routes>
    </MemoryRouter>,
  );
  return api.requisitionTrace;
}

describe('Trazabilidad documental', () => {
  afterEach(() => vi.restoreAllMocks());

  it('muestra las seis etapas completas y el porcentaje surtido', async () => {
    renderTrace();

    expect(await screen.findByTestId('trace-steps')).toBeInTheDocument();
    for (const stage of [
      'REQUISICION',
      'AUTORIZACION',
      'RESERVA',
      'ENTREGA',
      'VALE',
      'SEGUIMIENTO',
    ]) {
      expect(screen.getByTestId(`trace-stage-${stage}`)).toHaveTextContent('Completado');
    }
    expect(screen.getByTestId('trace-fulfillment')).toHaveTextContent('100 %');
  });

  it('relaciona el vale, sus impresiones y el evento de auditoría', async () => {
    renderTrace();

    expect(await screen.findByTestId('trace-voucher-VA-000166')).toBeInTheDocument();
    expect(screen.getByTestId('trace-audit-VOUCHER_CREATE')).toHaveTextContent('demo.almacenista');
    expect(screen.getByTestId('trace-voucher-VA-000166')).toHaveTextContent('RECEPCION SINTETICA');
    expect(screen.getByText(/VOUCHER_CREATED/)).toBeInTheDocument();
    expect(screen.getByText(/Impresiones:/)).toHaveTextContent('1');
  });
});
