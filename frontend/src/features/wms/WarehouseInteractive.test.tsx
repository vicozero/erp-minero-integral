import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type {
  Catalogs,
  ItemFamily,
  LocationInventory,
  LocationMap,
  MaterialSearchResult,
  User,
  WarehouseDashboard,
} from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { WarehouseInteractive } from './WarehouseInteractive';

// La escena real se verifica en navegador; en jsdom se sustituye por una
// proyección que expone los mismos identificadores de ubicación.
vi.mock('./Warehouse3D', () => ({
  default: ({ nodes }: { nodes: Array<{ id: string; code: string }> }) => (
    <div data-testid="mapa-3d">
      {nodes.map((node) => (
        <span key={node.id} data-location-id={node.id}>{node.code}</span>
      ))}
    </div>
  ),
}));

const VIEW_MAPS = ['warehouse.map.view'];
const VIEW_STOCK = ['warehouse.stock.view'];

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

const node = (id: string, code: string, x: string, occupied: string) => ({
  id,
  code,
  parent_id: null,
  hierarchy_path: `LAG / ALM_PRINCIPAL_DEMO / A / 01 / R1 / 1 / 01 / ${code}`,
  zone: 'A',
  aisle: '01',
  rack: 'R1',
  level: '1',
  position: '01',
  location_type: 'STANDARD',
  status: 'ACTIVE',
  coord_x: x,
  coord_y: '180',
  capacity_qty: '1000',
  occupied_qty: occupied,
  item_count: 1,
});

const map: LocationMap = {
  id: 'map-1',
  warehouse_id: 'wh-1',
  map_version: 3,
  label: 'Referencial · no es plano exacto',
  background_url: null,
  background_name: null,
  background_sha256: null,
  is_exact: false,
  width: '1000',
  height: '600',
  is_active: true,
  notes: null,
  nodes: [
    node('loc-1', 'A-01-R1-1-01', '260', '120'),
    node('loc-2', 'A-01-R1-2-01', '460', '0'),
  ],
};

const dashboard: WarehouseDashboard = {
  warehouse_id: 'wh-1',
  zone: null,
  family_id: null,
  totals: {
    location_count: 6,
    occupied: 3,
    empty: 3,
    blocked: 0,
    inactive: 0,
    capacity_defined_count: 6,
    capacity_qty: '6000',
    occupied_in_capacity_qty: '120',
    capacity_used_pct: '2.00',
  },
  alerts: {
    critical: [],
    below_minimum: [{
      item_id: 'item-1', code: 'DEMO-TORNILLO', description: 'Tornillo M8',
      uom_code: 'PZA', on_hand_qty: '5', reorder_point: '20', safety_stock: '10',
      location_count: 1, reason: 'Existencia por debajo del mínimo',
    }],
    unlocated: [],
  },
};

const inventory: LocationInventory = {
  location_id: 'loc-1',
  warehouse_id: 'wh-1',
  warehouse_code: 'ALM_PRINCIPAL_DEMO',
  code: 'A-01-R1-1-01',
  hierarchy_path: 'LAG / ALM_PRINCIPAL_DEMO / A / 01 / R1 / 1 / 01 / A-01-R1-1-01',
  zone: 'A', aisle: '01', rack: 'R1', level: '1', position: '01',
  location_type: 'STANDARD',
  status: 'ACTIVE',
  is_pickable: true,
  is_receivable: true,
  coord_x: '260', coord_y: '180',
  capacity_qty: '1000', occupied_qty: '120', occupancy_pct: '12.00', item_count: 1,
  items: [{
    item_id: 'item-1', code: 'DEMO-TORNILLO', description: 'Tornillo M8',
    manufacturer_part_no: 'FF-M8-30', internal_code: 'INT-001', lot_number: null,
    serial_number: null, on_hand_qty: '120', reserved_qty: '20', available_qty: '100',
    uom_code: 'PZA', unit_cost: '3.5000',
    last_movement: {
      id: 'mov-1', movement_no: 'MOV-0001', movement_type: 'RECEIPT', direction: 'IN',
      quantity: '120', balance_after_qty: '120', posted_at: '2026-11-19T10:00:00Z',
      source_document_type: 'INV_MOV',
    },
  }],
  last_movement: null,
  restrictions: [],
  can_view_cost: true,
  is_empty: false,
};

const searchResult: MaterialSearchResult = {
  query: 'TORNILLO',
  materials: [{
    item_id: 'item-1', code: 'DEMO-TORNILLO', description: 'Tornillo M8',
    manufacturer_part_no: 'FF-M8-30', internal_code: 'INT-001', family_name: 'CONSUMIBLES',
    uom_code: 'PZA', on_hand_qty: '120', available_qty: '100', location_count: 1,
    locations: [{
      location_id: 'loc-1', location_code: 'A-01-R1-1-01',
      hierarchy_path: 'LAG / ALM_PRINCIPAL_DEMO / A / 01 / R1 / 1 / 01 / A-01-R1-1-01',
      zone: 'A', aisle: '01', rack: 'R1', level: '1', position: '01',
      coord_x: '260', coord_y: '180', status: 'ACTIVE',
      on_hand_qty: '120', reserved_qty: '20', available_qty: '100',
    }],
  }],
  location_ids: ['loc-1'],
};

const catalogs: Catalogs = {
  mining_units: [], departments: [],
  warehouses: [
    { id: 'wh-1', code: 'ALM_PRINCIPAL_DEMO', name: 'Almacén principal' },
    { id: 'wh-2', code: 'ALM_AISLADO', name: 'Almacén aislado' },
  ],
  items: [], uoms: [], suppliers: [], cost_centers: [], equipment: [],
};

const families: ItemFamily[] = [{ id: 'fam-1', code: 'CONSUMIBLES', name: 'Consumibles', parent_id: null, is_active: true }];

function setup(permissions: string[] = [...VIEW_MAPS, ...VIEW_STOCK], overrides: Partial<LocationInventory> = {}) {
  vi.spyOn(api, 'catalogs').mockResolvedValue(catalogs);
  vi.spyOn(api, 'wmsFamilies').mockResolvedValue(families);
  vi.spyOn(api, 'wmsLocationMap').mockImplementation(async (id: string) =>
    id === 'wh-2' ? { ...map, warehouse_id: 'wh-2', nodes: [map.nodes[1]] } : map
  );
  vi.spyOn(api, 'wmsLocationMapVersions').mockResolvedValue([map]);
  vi.spyOn(api, 'locationQr').mockResolvedValue({
    location_id: 'loc-1', qr_token: 'WMS-opaco', svg_url: '/api/v1/wms/locations/loc-1/qr.svg',
    lookup_url: '/api/v1/wms/locations/lookup?qr_token=WMS-opaco',
  });
  vi.spyOn(api, 'wmsDashboard').mockImplementation(async (filters = {}) => ({
    ...dashboard,
    warehouse_id: filters.warehouse_id ?? null,
  }));
  const canViewCost = permissions.includes('warehouse.stock.view');
  const resolved = { ...inventory, ...overrides };
  vi.spyOn(api, 'wmsLocationInventory').mockResolvedValue({
    ...resolved,
    can_view_cost: canViewCost && resolved.can_view_cost,
    items: resolved.items.map((item) => ({
      ...item,
      unit_cost: canViewCost ? item.unit_cost : null,
    })),
  });
  vi.spyOn(api, 'wmsMaterialSearch').mockResolvedValue(searchResult);
  render(<AuthProvider initialUser={user(permissions)}><WarehouseInteractive /></AuthProvider>);
}

describe('Almacén virtual interactivo', () => {
  beforeEach(() => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({} as RenderingContext);
  });

  afterEach(() => vi.restoreAllMocks());

  it('carga plano referencial, KPIs y ficha de inventario real', async () => {
    setup();
    expect(await screen.findByText('A-01-R1-1-01')).toBeInTheDocument();
    expect(screen.getByText('6')).toBeInTheDocument();
    expect(screen.getAllByText(/Referencial · no es plano exacto/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('button', { name: /Ubicación A-01-R1-1-01/ }));
    const panel = await screen.findByTestId('panel-inventario');
    expect(within(panel).getByText('DEMO-TORNILLO')).toBeInTheDocument();
    expect(within(panel).getByText(/Costo 3.5/)).toBeInTheDocument();
    expect(within(panel).getByText(/Último movimiento: MOV-0001/)).toBeInTheDocument();
  });

  it('oculta el costo cuando el perfil no está autorizado', async () => {
    setup([...VIEW_MAPS]);
    fireEvent.click(await screen.findByRole('button', { name: /Ubicación A-01-R1-1-01/ }));
    const panel = await screen.findByTestId('panel-inventario');
    expect(within(panel).queryByText(/Costo/)).not.toBeInTheDocument();
    expect(within(panel).getByText(/no tiene autorización/)).toBeInTheDocument();
  });

  it('resalta las ubicaciones encontradas en la búsqueda de refacciones', async () => {
    setup();
    await screen.findByText('A-01-R1-1-01');
    fireEvent.change(screen.getByRole('searchbox', { name: 'Buscar refacciones' }), {
      target: { value: 'TORNILLO' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Localizar' }));

    await waitFor(() => expect(api.wmsMaterialSearch).toHaveBeenCalled());
    const highlighted = await screen.findByRole('button', { name: /Ubicación A-01-R1-1-01, Disponible/ });
    expect(highlighted.className).toContain('map-node-highlight');
    expect(screen.getByText(/1 ubicación\(es\)/)).toBeInTheDocument();
  });

  it('usa los mismos identificadores WMS en 2D y 3D', async () => {
    setup();
    const map2d = await screen.findByTestId('mapa-2d');
    expect(screen.queryByTestId('mapa-3d')).not.toBeInTheDocument();
    const ids2d = Array.from(map2d.querySelectorAll('[data-location-id]')).map((element) =>
      element.getAttribute('data-location-id'),
    );

    fireEvent.click(screen.getByRole('button', { name: 'Vista 3D' }));
    const scene = await screen.findByTestId('mapa-3d');
    const ids3d = Array.from(scene.querySelectorAll('[data-location-id]')).map((element) =>
      element.getAttribute('data-location-id'),
    );
    expect(ids2d).toEqual(['loc-1', 'loc-2']);
    expect(ids3d.sort()).toEqual(ids2d.sort());
  });

  it('muestra la vista 2D como alternativa cuando WebGL no está disponible', async () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    setup();
    await screen.findByTestId('mapa-2d');
    fireEvent.click(screen.getByRole('button', { name: 'Vista 3D' }));

    expect(await screen.findByText('WebGL no está disponible')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Volver a la vista 2D' }));
    expect(screen.getByTestId('mapa-2d')).toBeInTheDocument();
  });

  it('muestra estado vacío cuando la ubicación no tiene existencias', async () => {
    setup([...VIEW_MAPS], { is_empty: true, items: [], occupied_qty: '0' });
    fireEvent.click(await screen.findByRole('button', { name: /Ubicación A-01-R1-1-01/ }));
    const panel = await screen.findByTestId('panel-inventario');
    expect(within(panel).getByText('Esta ubicación no tiene existencias registradas.')).toBeInTheDocument();
  });

  it('impide consultar el plano a un perfil sin permiso', async () => {
    setup([]);
    expect(
      await screen.findByText('Su perfil no tiene permiso para consultar planos del almacén.'),
    ).toBeInTheDocument();
    expect(screen.queryByTestId('mapa-2d')).not.toBeInTheDocument();
  });

  it('aísla los almacenes al cambiar el selector', async () => {
    setup();
    await screen.findByTestId('mapa-2d');
    expect(screen.getByRole('button', { name: /Ubicación A-01-R1-2-01/ })).toBeInTheDocument();

    fireEvent.change(screen.getByRole('combobox', { name: 'Seleccionar almacén' }), {
      target: { value: 'wh-2' },
    });
    await waitFor(() => expect(api.wmsDashboard).toHaveBeenCalledWith(
      expect.objectContaining({ warehouse_id: 'wh-2' }),
    ));
    await waitFor(() => expect(screen.queryByRole('button', { name: /Ubicación A-01-R1-1-01/ })).not.toBeInTheDocument());
    expect(screen.getByRole('button', { name: /Ubicación A-01-R1-2-01/ })).toBeInTheDocument();
  });
});
