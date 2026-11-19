import { render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../../api/client';
import type { Requisition, User } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { History } from './History';

const requisition: Requisition = {
  id: 'req-1',
  document_no: 'REQ-LAG-2026-000001',
  department_id: 'dep-1',
  warehouse_id: null,
  equipment_id: null,
  cost_center_id: 'cc-1',
  requisition_type: 'STOCK',
  priority: 'NORMAL',
  status: 'APPROVED',
  justification: 'Prueba',
  observations: null,
  needed_at: null,
  submitted_at: null,
  approved_at: null,
  rejected_at: null,
  rejection_reason: null,
  work_order_no: null,
  created_at: '2026-11-19T09:00:00Z',
  lines: [],
};

function user(permissions: string[]): User {
  return {
    id: 'user-1',
    username: 'demo',
    email: 'demo@example.invalid',
    full_name: 'Demo',
    status: 'ACTIVE',
    roles: [],
    permissions,
    department_ids: [],
    must_change_password: false,
  };
}

function mockRequisitions(): void {
  vi.spyOn(api, 'requisitions').mockResolvedValue([requisition]);
  vi.spyOn(api, 'history').mockResolvedValue([{
    event_type: 'APPROVED',
    from_status: 'SUBMITTED',
    to_status: 'APPROVED',
    occurred_at: '2026-11-19T10:00:00Z',
    actor_id: '44444444-4444-4444-4444-444444444444',
    metadata: { approved_lines: 1 },
  }]);
}

function renderHistory(permissions: string[]) {
  return render(
    <AuthProvider initialUser={user(permissions)}>
      <History />
    </AuthProvider>,
  );
}

describe('Historial y bitácora', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('carga requisiciones aunque el usuario no tenga permiso de auditoría', async () => {
    mockRequisitions();
    vi.spyOn(api, 'audit').mockRejectedValue(new ApiError('Permiso requerido: auditoria.consultar', 403));

    renderHistory(['requisition.view', 'requisition.history.view']);

    expect(await screen.findByText('REQ-LAG-2026-000001')).toBeInTheDocument();
    expect(await screen.findByText(/Actor 44444444/)).toBeInTheDocument();
    expect(screen.getByText(/no cuenta con el permiso auditoria.consultar/)).toBeInTheDocument();
    expect(api.audit).not.toHaveBeenCalled();
  });

  it('muestra la bitácora y el identificador de solicitud cuando hay permiso', async () => {
    mockRequisitions();
    vi.spyOn(api, 'audit').mockResolvedValue([{
      id: 'audit-1',
      occurred_at: '2026-11-19T10:05:00Z',
      actor_username: 'demo.aprobador',
      action: 'APPROVE',
      entity_type: 'requisition',
      entity_id: 'req-1',
      detail: 'Autorización parcial',
      request_id: '55555555-5555-5555-5555-555555555555',
    }]);

    renderHistory(['requisition.view', 'requisition.history.view', 'audit.view']);

    expect(await screen.findByText('demo.aprobador')).toBeInTheDocument();
    expect(screen.getByText('55555555')).toBeInTheDocument();
    expect(api.audit).toHaveBeenCalled();
  });
});
