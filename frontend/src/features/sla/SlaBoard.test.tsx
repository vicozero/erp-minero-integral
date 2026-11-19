import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { api } from '../../api/client';
import type { Catalogs, SlaRequisition, User } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { SlaBoard } from './SlaBoard';

const user: User = {
  id: 'user-1',
  username: 'demo.admin',
  email: 'admin.demo@example.invalid',
  full_name: 'Administrador Demo',
  status: 'ACTIVE',
  roles: ['ADMIN'],
  permissions: ['sla.view', 'requisition.history.view'],
  department_ids: [],
  must_change_password: false,
};

const catalogs: Catalogs = {
  mining_units: [],
  departments: [{ id: 'dep-1', code: 'MNT', name: 'Mantenimiento' }],
  warehouses: [],
  items: [],
  uoms: [],
  suppliers: [],
  cost_centers: [],
  equipment: [{ id: 'eq-1', code: 'CAMION-07', name: 'Camión 07' }],
};

function row(color: 'GREEN' | 'YELLOW' | 'RED' | 'NONE', suffix: string): SlaRequisition {
  return {
    id: `req-${suffix}`,
    document_no: `REQ-LAG-2026-${suffix}`,
    department_id: 'dep-1',
    equipment_id: 'eq-1',
    requester_id: `user-${suffix}`,
    department_name: 'Mantenimiento',
    department_code: 'MNT',
    equipment: 'Camión 07',
    responsible: `Responsable ${suffix}`,
    status: 'APPROVED',
    administrative_status: 'APPROVED',
    priority: 'HIGH',
    requisition_type: 'STOCK',
    submitted_at: '2026-11-19T09:00:00Z',
    needed_at: '2026-11-20T09:00:00Z',
    pending_days: '1.50',
    fulfillment_percent: '40.00',
    sla: {
      color,
      label: color === 'RED' ? 'Vencida' : color === 'YELLOW' ? 'En riesgo' : color === 'GREEN' ? 'En plazo' : 'Sin medición',
      measured: color !== 'NONE',
      administrative_status: 'APPROVED',
      base_at: '2026-11-19T09:00:00Z',
      elapsed_hours: '2.00',
      green_deadline: '2026-11-20T09:00:00Z',
      yellow_deadline: '2026-11-21T09:00:00Z',
      policy_id: 'policy-1',
      policy_scope: 'GLOBAL/HIGH',
      emergency_active: false,
      message: null,
    },
  };
}

function mockApi(rows: SlaRequisition[]) {
  vi.spyOn(api, 'catalogs').mockResolvedValue(catalogs);
  return vi.spyOn(api, 'slaRequisitions').mockResolvedValue(rows);
}

function renderBoard(rows: SlaRequisition[]) {
  const list = mockApi(rows);
  render(
    <MemoryRouter>
      <AuthProvider initialUser={user}><SlaBoard /></AuthProvider>
    </MemoryRouter>,
  );
  return list;
}

describe('Semáforo de requisiciones', () => {
  afterEach(() => vi.restoreAllMocks());

  it('muestra el tablero con todas las columnas requeridas y totales por color', async () => {
    renderBoard([row('GREEN', '001'), row('YELLOW', '002'), row('RED', '003')]);

    expect(await screen.findByTestId('sla-row-REQ-LAG-2026-001')).toBeInTheDocument();
    expect(screen.getByTestId('sla-total-green')).toHaveTextContent('1');
    expect(screen.getByTestId('sla-total-yellow')).toHaveTextContent('1');
    expect(screen.getByTestId('sla-total-red')).toHaveTextContent('1');
    const headers = screen.getAllByRole('columnheader').map((node) => node.textContent);
    for (const label of [
      'Folio',
      'Departamento',
      'Equipo',
      'Responsable',
      'Estado administrativo',
      'Semáforo',
      'Fecha requerida',
      'Días pendientes',
      '% surtido',
    ]) {
      expect(headers).toContain(label);
    }
    expect(screen.getByTestId('sla-row-REQ-LAG-2026-001')).toHaveTextContent('Camión 07');
    expect(screen.getByTestId('sla-row-REQ-LAG-2026-001')).toHaveTextContent('40 %');
    expect(screen.getByTestId('sla-trace-REQ-LAG-2026-001').getAttribute('href')).toBe(
      '/trazabilidad/req-001',
    );
  });

  it('envía los filtros de color, departamento y fechas al backend', async () => {
    const list = renderBoard([row('RED', '003')]);
    await screen.findByTestId('sla-row-REQ-LAG-2026-003');

    fireEvent.change(screen.getByTestId('sla-filter-color'), { target: { value: 'RED' } });
    fireEvent.change(screen.getByTestId('sla-filter-department'), { target: { value: 'dep-1' } });
    fireEvent.change(screen.getByTestId('sla-filter-date-from'), { target: { value: '2026-11-01' } });
    fireEvent.change(screen.getByTestId('sla-filter-date-to'), { target: { value: '2026-11-30' } });

    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({
      sla_color: 'RED',
      department_id: 'dep-1',
      date_from: '2026-11-01',
      date_to: '2026-11-30',
    })));
  });

  it('limpia los filtros y conserva el semáforo separado del estado', async () => {
    const list = renderBoard([row('YELLOW', '002')]);
    await screen.findByTestId('sla-row-REQ-LAG-2026-002');
    expect(screen.getByTestId('sla-row-REQ-LAG-2026-002')).toHaveTextContent('Autorizada');
    expect(screen.getByTestId('sla-row-REQ-LAG-2026-002')).toHaveTextContent('En riesgo');

    fireEvent.change(screen.getByTestId('sla-filter-priority'), { target: { value: 'URGENT' } });
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ priority: 'URGENT' })));
    fireEvent.click(screen.getByTestId('sla-clear-filters'));
    await waitFor(() => expect(list).toHaveBeenLastCalledWith(expect.not.objectContaining({ priority: 'URGENT' })));
  });
});
