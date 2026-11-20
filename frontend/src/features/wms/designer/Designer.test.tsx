import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../../api/client';
import type {
  FloorPlan,
  FloorPlanWorkspace,
  LocationInventory,
  LocationMap,
  PlanElement,
  PlanPayload,
  RackBlueprintResult,
  User,
  WmsLocation,
} from '../../../api/types';
import { AuthProvider } from '../../../auth/AuthContext';
import { Designer } from './Designer';

// R3F no se inicializa en jsdom: se sustituye por una proyección que expone
// los mismos identificadores de elemento que el lienzo 2D.
vi.mock('./Designer3D', () => ({
  default: ({ elements }: { elements: Array<{ id: string; code?: string | null; name: string }> }) => (
    <div data-testid="designer-3d">
      {elements.map((element) => (
        <button key={element.id} type="button" data-designer-element-3d={element.id}>
          {element.code || element.name}
        </button>
      ))}
    </div>
  ),
}));

const user: User = {
  id: 'user-1',
  username: 'demo.almacenista',
  email: 'almacen.demo@example.invalid',
  full_name: 'Almacenista Demo',
  status: 'ACTIVE',
  roles: ['ALMACENISTA'],
  permissions: ['warehouse.plan.view', 'warehouse.plan.draft', 'warehouse.plan.publish'],
  department_ids: [],
  must_change_password: false,
};

const wall: PlanElement = {
  id: 'wall-1',
  type: 'WALL',
  name: 'Pared norte',
  code: null,
  x: 20,
  y: 20,
  width: 200,
  height: 8,
  depth: null,
  rotation: 0,
  color: '#475569',
  visible: true,
  locked: false,
  layer: 'estructura',
  z_index: 0,
  dimensions_verified: false,
  wms_location_id: null,
  properties: {},
};

const position: PlanElement = {
  ...wall,
  id: 'pos-1',
  type: 'POSITION',
  name: 'A-01-R1-1-01',
  code: 'A-01-R1-1-01',
  x: 260,
  y: 180,
  width: 30,
  height: 20,
  layer: 'posiciones',
  z_index: 1,
  wms_location_id: 'loc-1',
};

const plan: FloorPlan = {
  id: 'plan-1',
  warehouse_id: 'wh-1',
  plan_version: 1,
  status: 'DRAFT',
  label: 'Referencial · no es plano exacto',
  width: 1000,
  height: 600,
  grid_size: 20,
  scale_label: 'Referencial',
  dimensions_verified: false,
  elements: [wall, position],
  location_refs: [{ location_id: 'loc-1', element_id: 'pos-1', code: 'A-01-R1-1-01' }],
  revision: 1,
  is_active: false,
  notes: null,
  can_edit: true,
  can_publish: true,
  created_at: '2026-11-19T10:00:00Z',
  updated_at: null,
  published_at: null,
};

const workspace: FloorPlanWorkspace = { warehouse_id: 'wh-1', active: null, draft: plan, versions: [] };

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
  nodes: [],
};

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
  qr_token: 'WMS-opaco',
  capacity_qty: '1000',
  status: 'ACTIVE',
  is_pickable: true,
  is_receivable: true,
  coord_x: '260',
  coord_y: '180',
  hierarchy_path: 'LAG / ALM_PRINCIPAL_DEMO / A / 01 / R1 / 1 / 01',
  occupied_qty: '120',
  item_count: 1,
};

const inventory: LocationInventory = {
  location_id: 'loc-1',
  warehouse_id: 'wh-1',
  warehouse_code: 'ALM_PRINCIPAL_DEMO',
  code: 'A-01-R1-1-01',
  hierarchy_path: 'LAG / ALM_PRINCIPAL_DEMO / A / 01 / R1 / 1 / 01',
  zone: 'A',
  aisle: '01',
  rack: 'R1',
  level: '1',
  position: '01',
  location_type: 'STANDARD',
  status: 'ACTIVE',
  is_pickable: true,
  is_receivable: true,
  coord_x: '260',
  coord_y: '180',
  capacity_qty: '1000',
  occupied_qty: '120',
  occupancy_pct: '12.00',
  item_count: 1,
  items: [{
    item_id: 'item-1',
    code: 'DEMO-TORNILLO',
    description: 'Tornillo M8',
    manufacturer_part_no: 'FF-M8-30',
    internal_code: null,
    lot_number: null,
    serial_number: null,
    on_hand_qty: '120',
    reserved_qty: '20',
    available_qty: '100',
    uom_code: 'PZA',
    unit_cost: '3.5000',
    last_movement: null,
  }],
  last_movement: null,
  restrictions: [],
  can_view_cost: true,
  is_empty: false,
};

const rackResult: RackBlueprintResult = {
  element: {
    ...wall,
    id: 'rack-l7-01',
    type: 'RACK',
    name: 'Rack Lote 7',
    code: 'RACK-L7-01',
    layer: 'racks',
  },
  locations: [],
  created_count: 60,
  total_positions: 60,
  warning: 'Geometría referencial: no constituye un plano exacto ni modifica inventario.',
};

function setup() {
  vi.spyOn(api, 'wmsPlanWorkspace').mockResolvedValue(workspace);
  vi.spyOn(api, 'wmsPlanEnsureDraft').mockResolvedValue(plan);
  vi.spyOn(api, 'wmsLocationMap').mockResolvedValue(map);
  vi.spyOn(api, 'wmsLocations').mockResolvedValue([location]);
  vi.spyOn(api, 'wmsLocationInventory').mockResolvedValue(inventory);
  vi.spyOn(api, 'wmsPlanSave').mockResolvedValue({ ...plan, revision: 2 });
  vi.spyOn(api, 'wmsPlanCreateRack').mockResolvedValue(rackResult);
  vi.spyOn(api, 'wmsPlanPublish').mockResolvedValue(workspace);
  render(
    <AuthProvider initialUser={user}>
      <Designer
        warehouseId="wh-1"
        warehouseLabel="Almacén principal"
        canEdit
        canPublish
        canManageLocations
        canViewCost
        onClose={() => undefined}
      />
    </AuthProvider>,
  );
}

async function loadedCanvas() {
  return (await screen.findByRole('application', {
    name: 'Lienzo del diseñador de planos',
  })) as unknown as SVGSVGElement;
}

describe('Diseñador profesional de planos', () => {
  beforeEach(() => {
    // jsdom no implementa PointerEvent; sin este polyfill React no recibe
    // clientX/clientY y el cálculo de coordenadas del lienzo da NaN.
    class PointerEventPolyfill extends MouseEvent {
      pointerId: number;
      constructor(type: string, init: PointerEventInit = {}) {
        super(type, init);
        this.pointerId = init.pointerId ?? 1;
      }
    }
    Object.defineProperty(window, 'PointerEvent', {
      configurable: true, writable: true, value: PointerEventPolyfill,
    });
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
      x: 0, y: 0, width: 1000, height: 600, top: 0, left: 0,
      right: 1000, bottom: 600, toJSON: () => ({}),
    } as DOMRect);
    Object.defineProperty(Element.prototype, 'setPointerCapture', {
      configurable: true, writable: true, value: () => undefined,
    });
    Object.defineProperty(Element.prototype, 'releasePointerCapture', {
      configurable: true, writable: true, value: () => undefined,
    });
  });

  afterEach(() => vi.restoreAllMocks());

  it('carga la escena compartida y advierte que la geometría es referencial', async () => {
    setup();
    const canvas = await loadedCanvas();
    expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(2);
    expect(screen.getByText(/Borrador v1 · revisión 1/)).toBeInTheDocument();
    expect(screen.getByText(/Geometría referencial, no plano exacto/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Pared' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Asistente de rack' })).toBeInTheDocument();
  });

  it('muestra propiedades y existencias WMS reales al seleccionar una posición', async () => {
    setup();
    const canvas = await loadedCanvas();
    const group = canvas.querySelector('[data-element-id="pos-1"]');
    expect(group).not.toBeNull();
    fireEvent.pointerDown(group as Element, { clientX: 280, clientY: 190, button: 0, pointerId: 1 });

    const panel = await screen.findByRole('complementary', { name: 'Propiedades del objeto' });
    expect(within(panel).getAllByDisplayValue('A-01-R1-1-01').length).toBeGreaterThan(0);
    await waitFor(() => expect(api.wmsLocationInventory).toHaveBeenCalledWith('loc-1'));
    expect(await screen.findByText(/Datos WMS · A-01-R1-1-01/)).toBeInTheDocument();
    expect(screen.getByText(/Costo 3.5/)).toBeInTheDocument();
  });

  it('mueve un elemento con el mouse usando cuadrícula y guías', async () => {
    setup();
    const canvas = await loadedCanvas();
    const group = canvas.querySelector('[data-element-id="wall-1"]');
    expect(group).not.toBeNull();
    fireEvent.pointerDown(group as Element, { clientX: 100, clientY: 100, button: 0, pointerId: 1 });
    fireEvent.pointerMove(canvas, { clientX: 140, clientY: 100, button: 0, pointerId: 1 });
    fireEvent.pointerUp(canvas, { clientX: 140, clientY: 100, button: 0, pointerId: 1 });

    const panel = await screen.findByRole('complementary', { name: 'Propiedades del objeto' });
    await waitFor(() => expect(within(panel).getByDisplayValue('60')).toBeInTheDocument());
  });

  it('dibuja una pared y la conserva al deshacer y rehacer', async () => {
    setup();
    const canvas = await loadedCanvas();
    fireEvent.click(screen.getByRole('button', { name: 'Pared' }));
    fireEvent.pointerDown(canvas, { clientX: 100, clientY: 100, button: 0, pointerId: 1 });
    fireEvent.pointerMove(canvas, { clientX: 200, clientY: 100, button: 0, pointerId: 1 });
    fireEvent.pointerUp(canvas, { clientX: 200, clientY: 100, button: 0, pointerId: 1 });

    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(3));

    fireEvent.keyDown(window, { key: 'z', ctrlKey: true });
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(2));

    fireEvent.keyDown(window, { key: 'y', ctrlKey: true });
    await waitFor(() => expect(canvas.querySelectorAll('[data-element-id]')).toHaveLength(3));
  });

  it('guarda un borrador con la revisión optimista correcta', async () => {
    setup();
    await loadedCanvas();
    fireEvent.click(screen.getByRole('button', { name: 'Guardar borrador' }));
    await waitFor(() => expect(api.wmsPlanSave).toHaveBeenCalledTimes(1));
    const [planId, warehouseId, payload] = vi.mocked(api.wmsPlanSave).mock.calls[0];
    expect(planId).toBe('plan-1');
    expect(warehouseId).toBe('wh-1');
    expect((payload as PlanPayload).revision).toBe(1);
    expect((payload as PlanPayload).dimensions_verified).toBe(false);
    expect(await screen.findByText(/Borrador guardado en revisión 2/)).toBeInTheDocument();
  });

  it('crea un rack con posiciones desde el asistente sin tocar inventario', async () => {
    setup();
    await loadedCanvas();
    vi.mocked(api.wmsPlanWorkspace).mockResolvedValue({
      ...workspace,
      draft: { ...plan, revision: 2, elements: [...plan.elements, rackResult.element] },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Asistente de rack' }));
    const wizard = await screen.findByRole('dialog', { name: 'Asistente para crear rack' });
    expect(within(wizard).getByText(/posiciones potenciales/)).toHaveTextContent('60');
    fireEvent.submit(wizard);

    await waitFor(() => expect(api.wmsPlanCreateRack).toHaveBeenCalledTimes(1));
    expect(await screen.findByText(/60 posiciones potenciales · 60 ubicaciones WMS creadas/)).toBeInTheDocument();
    const canvas = await loadedCanvas();
    await waitFor(() => expect(canvas.querySelector('[data-element-id="rack-l7-01"]')).not.toBeNull());
  });

  it('usa el mismo modelo de escena en 2D y 3D', async () => {
    setup();
    const canvas = await loadedCanvas();
    const ids2d = Array.from(canvas.querySelectorAll('[data-element-id]')).map((element) =>
      element.getAttribute('data-element-id'),
    );

    fireEvent.click(screen.getByRole('button', { name: '3D' }));
    const scene = await screen.findByTestId('designer-3d');
    const ids3d = Array.from(scene.querySelectorAll('[data-designer-element-3d]')).map((element) =>
      element.getAttribute('data-designer-element-3d'),
    );
    expect(ids2d).toEqual(['wall-1', 'pos-1']);
    expect(ids3d.sort()).toEqual([...ids2d].sort());
  });

  it('impide publicar cuando el perfil no tiene permiso de publicación', async () => {
    vi.spyOn(api, 'wmsPlanWorkspace').mockResolvedValue(workspace);
    vi.spyOn(api, 'wmsPlanPublish').mockResolvedValue(workspace);
    vi.spyOn(api, 'wmsLocationMap').mockResolvedValue(map);
    vi.spyOn(api, 'wmsLocations').mockResolvedValue([location]);
    render(
      <AuthProvider initialUser={user}>
        <Designer
          warehouseId="wh-1"
          warehouseLabel="Almacén principal"
          canEdit
          canPublish={false}
          canManageLocations={false}
          canViewCost={false}
          onClose={() => undefined}
        />
      </AuthProvider>,
    );
    await loadedCanvas();
    expect(screen.getByRole('button', { name: 'Publicar versión' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Guardar borrador' })).toBeEnabled();
    expect(api.wmsPlanPublish).not.toHaveBeenCalled();
  });
});
