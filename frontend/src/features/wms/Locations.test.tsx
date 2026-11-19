import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { Catalogs, User, WmsLocation, WmsLocationDetail } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { Locations } from './Locations';

const user = (permissions: string[]): User => ({
  id: 'user-1',
  username: 'demo.almacenista',
  email: 'almacen.demo@example.invalid',
  full_name: 'Almacenista Demo',
  status: 'ACTIVE',
  roles: ['ALMACENISTA'],
  permissions,
  department_ids: [],
  must_change_password: false,
});

const location: WmsLocation = {
  id: 'loc-1',
  warehouse_id: 'wh-1',
  warehouse_code: 'ALM_PRINCIPAL_DEMO',
  code: 'A-01-R1-1-01',
  zone: 'A',
  aisle: '01',
  rack: 'R1',
  level: '1',
  position: '01',
  location_type: 'STANDARD',
  qr_token: 'WMS:ALM_PRINCIPAL_DEMO:A-01-R1-1-01',
  capacity_qty: '1000',
  status: 'ACTIVE',
  is_pickable: true,
  is_receivable: true,
  occupied_qty: '120.000000',
  item_count: 1,
};

const detail: WmsLocationDetail = {
  ...location,
  restrictions: [{ item_family_id: null, item_id: null, max_qty: '250', allows_lot_mix: true, allows_serial_mix: false }],
  items: [{
    location_id: 'loc-1',
    location_code: location.code,
    warehouse_code: location.warehouse_code,
    zone: 'A',
    aisle: '01',
    lot_number: 'LOT-DEMO-001',
    on_hand_qty: '120.000000',
    reserved_qty: '0.000000',
    available_qty: '120.000000',
  }],
};

function mockLocations(permissions: string[]) {
  const catalogs: Catalogs = {
    mining_units: [],
    departments: [],
    warehouses: [{ id: 'wh-1', code: 'ALM_PRINCIPAL_DEMO', name: 'Almacén principal' }],
    items: [],
    uoms: [],
    suppliers: [],
    cost_centers: [],
    equipment: [],
  };
  vi.spyOn(api, 'catalogs').mockResolvedValue(catalogs);
  vi.spyOn(api, 'wmsLocations').mockResolvedValue([location]);
  vi.spyOn(api, 'wmsLocationDetail').mockResolvedValue(detail);
  const create = vi.spyOn(api, 'createLocation').mockResolvedValue({
    ...location,
    id: 'loc-2',
    code: 'QA-A-99-01',
    qr_token: 'WMS:ALM_PRINCIPAL_DEMO:QA-A-99-01',
  });
  return { create, permissions };
}

function renderLocations(permissions: string[]) {
  const mocks = mockLocations(permissions);
  render(<AuthProvider initialUser={user(permissions)}><Locations /></AuthProvider>);
  return mocks;
}

describe('Ubicaciones WMS', () => {
  afterEach(() => vi.restoreAllMocks());

  it('muestra ocupación derivada y el token de etiqueta en la ficha', async () => {
    renderLocations(['warehouse.location.view', 'warehouse.location.manage']);

    expect(await screen.findByRole('button', { name: 'Ver ficha de A-01-R1-1-01' })).toBeInTheDocument();
    expect(screen.getByText(/120 \/ 1,000/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Ver ficha de A-01-R1-1-01' }));

    expect(await screen.findByText('WMS:ALM_PRINCIPAL_DEMO:A-01-R1-1-01')).toBeInTheDocument();
    expect(screen.getByText(/LOT-DEMO-001/)).toBeInTheDocument();
  });

  it('envía el alta con almacén, código y tipo seleccionados', async () => {
    const { create } = renderLocations(['warehouse.location.view', 'warehouse.location.manage']);

    await screen.findByRole('button', { name: 'Ver ficha de A-01-R1-1-01' });
    fireEvent.change(screen.getByLabelText('Código de la nueva ubicación'), {
      target: { value: 'QA-A-99-01' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Crear ubicación' }));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    expect(create.mock.calls[0][0]).toEqual(expect.objectContaining({
      warehouse_id: 'wh-1',
      code: 'QA-A-99-01',
      location_type: 'STANDARD',
    }));
  });

  it('oculta el formulario de altas sin permiso de administración', async () => {
    renderLocations(['warehouse.location.view']);

    expect(await screen.findByRole('button', { name: 'Ver ficha de A-01-R1-1-01' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Nueva ubicación' })).not.toBeInTheDocument();
  });
});
