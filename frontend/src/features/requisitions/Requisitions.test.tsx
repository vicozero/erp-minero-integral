import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { Catalogs, Requisition, WmsItem } from '../../api/types';
import { Requisitions } from './Requisitions';

const UOM_ID = '11111111-1111-1111-1111-111111111111';
const ITEM_ID = '22222222-2222-2222-2222-222222222222';

function catalogs(): Catalogs {
  return {
    mining_units: [],
    departments: [{ id: 'dep-1', code: 'MNT', name: 'Mantenimiento' }],
    warehouses: [{ id: 'wh-1', code: 'ALM', name: 'Almacén central' }],
    items: [],
    uoms: [{ id: UOM_ID, code: 'UND', name: 'Unidad' }],
    suppliers: [],
    cost_centers: [{ id: 'cc-1', code: 'CC1', name: 'Costo mina' }],
    equipment: [{ id: 'eq-1', code: 'EQ1', name: 'Camión 01' }],
  };
}

function requisition(status: string): Requisition {
  return {
    id: 'req-1',
    document_no: 'REQ-LAG-2026-000001',
    department_id: 'dep-1',
    warehouse_id: 'wh-1',
    equipment_id: null,
    cost_center_id: 'cc-1',
    requisition_type: 'STOCK',
    priority: 'NORMAL',
    status,
    justification: 'Reposición de inventario de seguridad',
    observations: null,
    needed_at: null,
    submitted_at: status === 'DRAFT' ? null : '2026-11-19T10:00:00Z',
    approved_at: null,
    rejected_at: null,
    rejection_reason: null,
    work_order_no: null,
    created_at: '2026-11-19T09:00:00Z',
    lines: [{
      id: 'line-1',
      line_no: 1,
      item_id: ITEM_ID,
      description: 'Filtro hidráulico',
      uom_id: UOM_ID,
      requested_qty: '4',
      authorised_qty: '0',
      cancelled_qty: '0',
      status: 'PENDING',
      notes: null,
      reserved_qty: '0',
      purchased_qty: '0',
      received_qty: '0',
      delivered_qty: '0',
      pending_qty: '0',
    }],
  };
}

function wmsItem(): WmsItem {
  return {
    id: ITEM_ID,
    code: 'FIL-HID-01',
    description: 'Filtro hidráulico 10 micras',
    family_id: null,
    family_name: null,
    manufacturer: 'Ficticio S.A.',
    manufacturer_part_no: 'PART-98765',
    barcode: null,
    uom_id: UOM_ID,
    uom_code: 'UND',
    standard_cost: '0',
    lot_tracked: false,
    serial_tracked: false,
    is_consumable: true,
    is_returnable: false,
    is_tool: false,
    is_active: true,
    on_hand_qty: '12',
    reserved_qty: '0',
    available_qty: '12',
    location_count: 1,
  };
}

function mockApi(status = 'DRAFT') {
  vi.spyOn(api, 'catalogs').mockResolvedValue(catalogs());
  vi.spyOn(api, 'requisitions').mockResolvedValue([requisition(status)]);
  vi.spyOn(api, 'wmsSearchItems').mockResolvedValue([wmsItem()]);
  return {
    create: vi.spyOn(api, 'createRequisition').mockResolvedValue(requisition('DRAFT')),
    submit: vi.spyOn(api, 'submitRequisition').mockResolvedValue(requisition('SUBMITTED')),
    update: vi.spyOn(api, 'updateRequisitionDraft').mockResolvedValue(requisition('DRAFT')),
    cancel: vi.spyOn(api, 'cancelRequisition').mockResolvedValue(requisition('CANCELLED')),
    history: vi.spyOn(api, 'history').mockResolvedValue([{
      event_type: 'CREATED',
      from_status: null,
      to_status: 'DRAFT',
      occurred_at: '2026-11-19T09:00:00Z',
      actor_id: '33333333-3333-3333-3333-333333333333',
      metadata: { origin: 'portal' },
    }]),
  };
}

async function openForm(): Promise<void> {
  await screen.findAllByText('REQ-LAG-2026-000001');
  fireEvent.click(screen.getByRole('button', { name: 'Nueva requisición' }));
}

describe('Mejora de requisiciones', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('busca artículos por número de parte y completa la partida', async () => {
    mockApi();
    render(<Requisitions />);
    await openForm();

    fireEvent.click(screen.getByRole('button', { name: 'Seleccionar artículo' }));
    fireEvent.change(await screen.findByPlaceholderText('Código, descripción o número de parte'), {
      target: { value: 'PART-98765' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }));

    const result = await screen.findByRole('listitem');
    expect(result).toHaveTextContent('PART-98765');
    fireEvent.click(result);

    expect(screen.getAllByDisplayValue('Filtro hidráulico 10 micras')).toHaveLength(2);
    expect(screen.getByText('FIL-HID-01')).toBeInTheDocument();
    expect(api.wmsSearchItems).toHaveBeenCalledWith(expect.objectContaining({ query: 'PART-98765' }));
  });

  it('valida la cantidad por partida antes de enviar', async () => {
    const { create } = mockApi();
    render(<Requisitions />);
    await openForm();

    const quantity = screen.getByLabelText('Cantidad solicitada');
    fireEvent.change(quantity, { target: { value: '0' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar y enviar' }));

    expect(await screen.findByText('La cantidad debe ser mayor a cero.')).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it('edita un borrador con PATCH en lugar de crear otro documento', async () => {
    const { update } = mockApi('DRAFT');
    render(<Requisitions />);
    await screen.findAllByText('REQ-LAG-2026-000001');

    fireEvent.click(screen.getByRole('button', { name: 'Editar' }));
    fireEvent.change(await screen.findByLabelText('Justificación *'), {
      target: { value: 'Reposición urgente de filtros' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar borrador' }));

    await waitFor(() => expect(update).toHaveBeenCalledTimes(1));
    expect(update.mock.calls[0][0]).toBe('req-1');
    expect(update.mock.calls[0][1]).toMatchObject({
      justification: 'Reposición urgente de filtros',
      lines: [expect.objectContaining({ id: 'line-1' })],
    });
  });

  it('pide confirmación y motivo antes de cancelar', async () => {
    const { cancel } = mockApi('SUBMITTED');
    render(<Requisitions />);
    await screen.findAllByText('REQ-LAG-2026-000001');

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(screen.getByRole('dialog')).toHaveTextContent('Cancelar requisición');
    fireEvent.change(screen.getByLabelText('Motivo de la cancelación'), {
      target: { value: 'Cancelación de prueba' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar requisición' }));

    await waitFor(() => expect(cancel).toHaveBeenCalledWith('req-1', 'Cancelación de prueba'));
  });

  it('muestra el actor del evento en el seguimiento', async () => {
    mockApi('SUBMITTED');
    render(<Requisitions />);
    await screen.findAllByText('REQ-LAG-2026-000001');

    fireEvent.click(screen.getByRole('button', { name: 'Seguimiento' }));
    expect(await screen.findByText(/Actor 33333333/)).toBeInTheDocument();
  });
});
