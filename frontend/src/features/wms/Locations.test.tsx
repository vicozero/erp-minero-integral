import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type {
  Catalogs,
  LocationMap,
  LocationQr,
  User,
  WmsLocation,
  WmsLocationDetail,
} from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { Locations } from './Locations';

const VIEW = ['warehouse.location.view', 'warehouse.map.view'];
const MANAGE_LOCATIONS = ['warehouse.location.manage'];
const MANAGE_MAPS = ['warehouse.map.manage'];

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
  parent_id: null,
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
  coord_x: '260.0000',
  coord_y: '180.0000',
  hierarchy_path: 'LAG / ALM_PRINCIPAL_DEMO / A / 01 / R1 / 1 / 01 / A-01-R1-1-01',
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

const map: LocationMap = {
  id: 'map-1',
  warehouse_id: 'wh-1',
  map_version: 1,
  label: 'Referencial · no es plano exacto',
  background_url: null,
  background_name: null,
  background_sha256: null,
  is_exact: false,
  width: '1000',
  height: '600',
  is_active: true,
  notes: null,
  nodes: [location],
};

const qr: LocationQr = {
  location_id: 'loc-1',
  qr_token: 'WMS-opaco-sin-almacen-ni-codigo',
  svg_url: '/api/v1/wms/locations/loc-1/qr.svg',
  lookup_url: '/api/v1/wms/locations/locationQr?qr_token=WMS-opaco-sin-almacen-ni-codigo',
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
  vi.spyOn(api, 'wmsLocationMap').mockResolvedValue(map);
  vi.spyOn(api, 'wmsLocationMapVersions').mockResolvedValue([map]);
  vi.spyOn(api, 'locationQr').mockResolvedValue(qr);
  const updateCoordinates = vi.spyOn(api, 'updateLocationCoordinates').mockResolvedValue({
    id: 'loc-1',
    coord_x: '300.0000',
    coord_y: '250.0000',
    version: 2,
  });
  const create = vi.spyOn(api, 'createLocation').mockResolvedValue({
    ...location,
    id: 'loc-2',
    code: 'QA-A-99-01',
    qr_token: 'WMS-token-opaco-nuevo',
  });
  return { create, updateCoordinates, permissions };
}

function renderLocations(permissions: string[]) {
  const mocks = mockLocations(permissions);
  render(<AuthProvider initialUser={user(permissions)}><Locations /></AuthProvider>);
  return mocks;
}

describe('Ubicaciones WMS', () => {
  afterEach(() => vi.restoreAllMocks());

  it('muestra ocupación derivada y el token de etiqueta en la ficha', async () => {
    renderLocations([...VIEW, ...MANAGE_LOCATIONS]);

    expect(await screen.findByRole('button', { name: 'Ver ficha de A-01-R1-1-01' })).toBeInTheDocument();
    expect(screen.getByText(/120 \/ 1,000/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Ver ficha de A-01-R1-1-01' }));

    expect(await screen.findByText('WMS:ALM_PRINCIPAL_DEMO:A-01-R1-1-01')).toBeInTheDocument();
    expect(screen.getByText(/LOT-DEMO-001/)).toBeInTheDocument();
  });

  it('envía el alta con almacén, código y tipo seleccionados', async () => {
    const { create } = renderLocations([...VIEW, ...MANAGE_LOCATIONS]);

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
    renderLocations(VIEW);

    expect(await screen.findByRole('button', { name: 'Ver ficha de A-01-R1-1-01' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Nueva ubicación' })).not.toBeInTheDocument();
  });

  it('muestra el plano como referencial y abre la ficha al seleccionar un nodo', async () => {
    renderLocations([...VIEW, ...MANAGE_MAPS]);

    expect(document.querySelector('.map-disclaimer')).toHaveTextContent('no es plano exacto');
    const node = await screen.findByRole('button', { name: 'Ubicación A-01-R1-1-01 en el plano' });
    fireEvent.click(node);

    const sidebar = within(screen.getByRole('complementary', { name: 'Panel lateral de ubicación' }));
    expect(await sidebar.findByRole('heading', { name: 'A-01-R1-1-01' })).toBeInTheDocument();
    expect(screen.getByText(/LAG \/ ALM_PRINCIPAL_DEMO \/ A \/ 01/)).toBeInTheDocument();
    expect(await screen.findByText(qr.qr_token)).toBeInTheDocument();
    expect(screen.queryByText(/\/api\/v1\/wms\/locations\/lookup/)).not.toBeInTheDocument();
  });

  it('guarda coordenadas del plano sin editar existencias', async () => {
    const { updateCoordinates } = renderLocations([...VIEW, ...MANAGE_MAPS]);

    const node = await screen.findByRole('button', { name: 'Ubicación A-01-R1-1-01 en el plano' });
    fireEvent.click(node);
    const sidebar = within(screen.getByRole('complementary', { name: 'Panel lateral de ubicación' }));
    await sidebar.findByRole('heading', { name: 'A-01-R1-1-01' });

    fireEvent.change(screen.getByLabelText('Coordenada X de la ubicación'), { target: { value: '300' } });
    fireEvent.change(screen.getByLabelText('Coordenada Y de la ubicación'), { target: { value: '250' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar coordenadas' }));

    await waitFor(() => expect(updateCoordinates).toHaveBeenCalledWith('loc-1', '300', '250'));
    expect(await screen.findByText(/Coordenadas guardadas/)).toBeInTheDocument();
  });

  it('oculta la administración del mapa y bloquea coordenadas sin permiso', async () => {
    renderLocations(VIEW);

    const node = await screen.findByRole('button', { name: 'Ubicación A-01-R1-1-01 en el plano' });
    fireEvent.click(node);

    expect(await screen.findByLabelText('Coordenada X de la ubicación')).toBeDisabled();
    expect(screen.queryByRole('button', { name: 'Guardar coordenadas' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Guardar nueva versión' })).not.toBeInTheDocument();
  });
});
