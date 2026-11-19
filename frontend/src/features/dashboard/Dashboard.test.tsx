import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, ApiError } from '../../api/client';
import type { Requisition, User } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { Dashboard } from './Dashboard';

const UOM_ID = '11111111-1111-1111-1111-111111111111';

function line(id: string, qty: string, authorised: string, delivered: string) {
  return {
    id,
    line_no: 1,
    item_id: null,
    description: 'Artículo',
    uom_id: UOM_ID,
    requested_qty: qty,
    authorised_qty: authorised,
    cancelled_qty: '0',
    status: 'AUTHORISED',
    notes: null,
    reserved_qty: '0',
    purchased_qty: '0',
    received_qty: '0',
    delivered_qty: delivered,
    pending_qty: String(Number(authorised) - Number(delivered)),
  };
}

function requisition(id: string, status: string, submittedAt: string | null, approvedAt: string | null): Requisition {
  return {
    id,
    document_no: `REQ-LAG-2026-${id}`,
    department_id: 'dep-1',
    warehouse_id: null,
    equipment_id: null,
    cost_center_id: 'cc-1',
    requisition_type: 'STOCK',
    priority: 'NORMAL',
    status,
    justification: 'Prueba',
    observations: null,
    needed_at: null,
    submitted_at: submittedAt,
    approved_at: approvedAt,
    rejected_at: null,
    rejection_reason: null,
    work_order_no: null,
    created_at: '2026-11-19T09:00:00Z',
    lines: [line(`${id}-line`, '10', '8', '6')],
  };
}

const user: User = {
  id: 'user-1',
  username: 'demo',
  email: 'demo@example.invalid',
  full_name: 'Demo',
  status: 'ACTIVE',
  roles: [],
  permissions: ['requisition.view', 'purchase.view', 'catalog.view'],
  department_ids: [],
  must_change_password: false,
};

function mockCatalogs(): void {
  vi.spyOn(api, 'catalogs').mockResolvedValue({
    mining_units: [],
    departments: [],
    warehouses: [],
    items: [],
    uoms: [{ id: UOM_ID, code: 'UND', name: 'Unidad' }],
    suppliers: [],
    cost_centers: [],
    equipment: [],
  });
}

function renderDashboard() {
  return render(
    <MemoryRouter>
      <AuthProvider initialUser={user}>
        <Dashboard />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Dashboard con datos reales de API', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('calcula pendientes, surtido por unidad y tiempo medio de autorización', async () => {
    vi.spyOn(api, 'requisitions').mockResolvedValue([
      requisition('000001', 'SUBMITTED', '2026-11-19T09:00:00Z', null),
      requisition('000002', 'APPROVED', '2026-11-19T10:00:00Z', '2026-11-19T11:00:00Z'),
    ]);
    vi.spyOn(api, 'purchases').mockResolvedValue([]);
    vi.spyOn(api, 'audit').mockResolvedValue([]);
    mockCatalogs();

    renderDashboard();

    expect(await screen.findByText('Centro de operaciones')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText('1.0 h')).toBeInTheDocument());
    expect(screen.getByText(/Indicadores no disponibles con la API actual/)).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: 'Unidad' })).toBeInTheDocument();
    expect(screen.getAllByText('UND').length).toBeGreaterThan(0);
    expect(screen.getByText('Materiales pendientes')).toBeInTheDocument();
    expect(api.audit).not.toHaveBeenCalled();
  });

  it('degrada parcialmente si falla el servicio de compras', async () => {
    vi.spyOn(api, 'requisitions').mockResolvedValue([requisition('000001', 'SUBMITTED', null, null)]);
    vi.spyOn(api, 'purchases').mockRejectedValue(new ApiError('Error interno', 500));
    mockCatalogs();

    renderDashboard();

    expect(await screen.findByText(/No se pudieron cargar: compras/)).toBeInTheDocument();
    expect(screen.getByText('REQ-LAG-2026-000001')).toBeInTheDocument();
    expect(screen.getByText('N/D')).toBeInTheDocument();
  });
});
