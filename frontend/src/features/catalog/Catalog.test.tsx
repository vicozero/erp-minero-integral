import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { Catalogs, ItemFamily, User, WmsItem, WmsItemDetail } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { Catalog } from './Catalog';

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

const family: ItemFamily = {
  id: 'family-1',
  code: 'CONSUMIBLES',
  name: 'Consumibles y ferretería',
  parent_id: null,
  is_active: true,
};

const item: WmsItem = {
  id: 'item-1',
  code: 'DEMO-TORNILLO',
  description: 'Tornillo M8 x 30 (demo)',
  family_id: family.id,
  family_name: family.name,
  manufacturer: 'Fabricante Ficticio S.A.',
  manufacturer_part_no: 'FF-M8-30',
  barcode: '7500000000017',
  uom_id: 'uom-1',
  uom_code: 'UND',
  standard_cost: '2.5000',
  lot_tracked: true,
  serial_tracked: false,
  is_consumable: true,
  is_returnable: false,
  is_tool: false,
  is_active: true,
  on_hand_qty: '120.000000',
  reserved_qty: '0.000000',
  available_qty: '120.000000',
  location_count: 1,
};

const detail: WmsItemDetail = {
  ...item,
  image_url: null,
  supplier_name: 'Proveedor ficticio demo',
  default_supplier_id: 'supplier-1',
  reorder_point: '20',
  safety_stock: '10',
  max_stock: '500',
  weight_kg: null,
  volume_m3: null,
  storage_temperature_min: null,
  storage_temperature_max: null,
  locations: [{
    location_id: 'loc-1',
    location_code: 'A-01-R1-1-01',
    warehouse_code: 'ALM_PRINCIPAL_DEMO',
    zone: 'A',
    aisle: '01',
    lot_number: 'LOT-DEMO-001',
    on_hand_qty: '120.000000',
    reserved_qty: '0.000000',
    available_qty: '120.000000',
  }],
  lots: [{
    id: 'lot-1',
    lot_number: 'LOT-DEMO-001',
    status: 'ACTIVE',
    manufactured_at: null,
    expiry_date: null,
  }],
  serials: [],
  cross_references: [],
  suppliers: [],
  movements: [],
  related_documents: [],
};

function mockCatalog(permissions: string[] = ['catalog.view', 'catalog.manage']) {
  const catalogs: Catalogs = {
    mining_units: [],
    departments: [],
    warehouses: [{ id: 'wh-1', code: 'ALM_PRINCIPAL_DEMO', name: 'Almacén principal' }],
    items: [],
    uoms: [],
    suppliers: [],
    cost_centers: [],
    equipment: [{ id: 'eq-1', code: 'EQ-1', name: 'Equipo demo' }],
  };
  const search = vi.spyOn(api, 'wmsSearchItems').mockResolvedValue([item]);
  vi.spyOn(api, 'wmsFamilies').mockResolvedValue([family]);
  vi.spyOn(api, 'wmsLocations').mockResolvedValue([]);
  vi.spyOn(api, 'catalogs').mockResolvedValue(catalogs);
  const detailSpy = vi.spyOn(api, 'wmsItemDetail').mockResolvedValue(detail);
  return { search, detailSpy, permissions };
}

function renderCatalog(permissions: string[] = ['catalog.view', 'catalog.manage']) {
  const mocks = mockCatalog(permissions);
  render(<AuthProvider initialUser={user(permissions)}><Catalog /></AuthProvider>);
  return mocks;
}

describe('Catálogo WMS', () => {
  afterEach(() => vi.restoreAllMocks());

  it('busca por texto y muestra la ficha con ubicación y lote', async () => {
    const { search } = renderCatalog();

    expect(await screen.findByRole('button', { name: 'Ver ficha de DEMO-TORNILLO' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('Buscar por texto, código o código de barras'), {
      target: { value: 'TORNILLO' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }));
    await waitFor(() => expect(search).toHaveBeenCalledWith(expect.objectContaining({ query: 'TORNILLO' })));

    fireEvent.click(await screen.findByRole('button', { name: 'Ver ficha de DEMO-TORNILLO' }));
    expect(await screen.findByText('Fabricante Ficticio S.A.')).toBeInTheDocument();
    expect(screen.getByText('A-01-R1-1-01')).toBeInTheDocument();
    expect(screen.getAllByText(/LOT-DEMO-001/).length).toBeGreaterThanOrEqual(2);
  });

  it('oculta las altas al usuario sin permiso de administración', async () => {
    renderCatalog(['catalog.view']);

    expect(await screen.findByRole('button', { name: 'Ver ficha de DEMO-TORNILLO' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Nueva familia' })).not.toBeInTheDocument();
  });
});
