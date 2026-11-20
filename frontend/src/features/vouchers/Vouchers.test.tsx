import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { Catalogs, RenderRecord, Requisition, User, Voucher } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { Vouchers } from './Vouchers';

const PERMISSIONS = [
  'document.render',
  'warehouse.voucher.create',
  'warehouse.voucher.issue',
];

const user: User = {
  id: 'user-1',
  username: 'demo.almacenista',
  email: 'almacen.demo@example.invalid',
  full_name: 'Almacenista Demo',
  status: 'ACTIVE',
  roles: ['ALMACENISTA'],
  permissions: PERMISSIONS,
  department_ids: [],
  must_change_password: false,
};

const catalogs: Catalogs = {
  mining_units: [],
  departments: [{ id: 'dep-1', code: 'MNT', name: 'Mantenimiento' }],
  warehouses: [{ id: 'wh-1', code: 'ALM', name: 'Almacén central' }],
  items: [],
  uoms: [],
  suppliers: [],
  cost_centers: [{ id: 'cc-1', code: 'CC-MINA', name: 'Costo mina' }],
  equipment: [],
};

const requisition: Requisition = {
  id: 'req-1',
  document_no: 'REQ-LAG-2026-000001',
  department_id: 'dep-1',
  warehouse_id: 'wh-1',
  equipment_id: null,
  cost_center_id: 'cc-1',
  requisition_type: 'STOCK',
  priority: 'NORMAL',
  status: 'APPROVED',
  justification: 'Prueba de vale',
  observations: null,
  needed_at: null,
  submitted_at: null,
  approved_at: '2026-11-19T10:00:00Z',
  rejected_at: null,
  rejection_reason: null,
  work_order_no: 'OT-001',
  created_at: '2026-11-19T09:00:00Z',
  lines: [{
    id: 'line-1',
    line_no: 1,
    item_id: null,
    description: 'Refacción sintética',
    uom_id: 'uom-1',
    requested_qty: '2',
    authorised_qty: '2',
    cancelled_qty: '0',
    status: 'APPROVED',
    notes: null,
    reserved_qty: '0',
    purchased_qty: '0',
    received_qty: '0',
    delivered_qty: '0',
    pending_qty: '2',
  }],
};

const voucher: Voucher = {
  id: 'va-1',
  document_no: 'VA-000166',
  department_id: 'dep-1',
  warehouse_id: 'wh-1',
  source_requisition_id: 'req-1',
  cost_center_code: 'CC-MINA',
  area: 'MECANICA',
  usage_equipment: 'CAMION 07',
  issue_date: '2026-11-19',
  status: 'DRAFT',
  template_code: 'VA_CARTA',
  template_version: 1,
  issued_at: null,
  created_at: '2026-11-19T11:00:00Z',
  received_by_name: null,
  authorized_by_name: null,
  dispatched_by_name: null,
  signatures_recorded_at: null,
  lines: [],
};

const renderRecord: RenderRecord = {
  id: 'render-1',
  document_no: 'VA-000166',
  document_format: 'PDF',
  sha256: 'a'.repeat(64),
  size_bytes: 4096,
  is_reprint: false,
  rendered_at: '2026-11-19T11:02:00Z',
  source_render_id: null,
};

function mockApi(hasVoucher = false) {
  vi.spyOn(api, 'catalogs').mockResolvedValue(catalogs);
  vi.spyOn(api, 'requisitions').mockResolvedValue([requisition]);
  const vouchersSpy = vi.spyOn(api, 'vouchers');
  if (hasVoucher) {
    vouchersSpy.mockResolvedValue([voucher]);
  } else {
    // Primera carga sin vales; después de crear, el vale aparece en el historial.
    vouchersSpy.mockResolvedValueOnce([]).mockResolvedValue([voucher]);
  }
  return {
    create: vi.spyOn(api, 'createVoucher').mockResolvedValue(voucher),
    issue: vi.spyOn(api, 'issueVoucher').mockResolvedValue({ ...voucher, status: 'ISSUED' }),
    sign: vi.spyOn(api, 'signVoucher').mockResolvedValue({
      ...voucher,
      received_by_name: 'RECEPCION SINTETICA',
      authorized_by_name: 'AUTORIZACION SINTETICA',
      dispatched_by_name: 'DESPACHO SINTETICO',
      signatures_recorded_at: '2026-11-19T11:05:00Z',
    }),
    renders: vi.spyOn(api, 'documentRenders').mockResolvedValue([renderRecord]),
  };
}

function renderVouchers(hasVoucher = false) {
  const mocks = mockApi(hasVoucher);
  render(<AuthProvider initialUser={user}><Vouchers /></AuthProvider>);
  return mocks;
}

describe('Vales de almacén', () => {
  afterEach(() => vi.restoreAllMocks());

  it('genera un vale desde una requisición autorizada y ofrece PDF y Excel', async () => {
    const { create } = renderVouchers();

    fireEvent.change(await screen.findByTestId('voucher-requisition'), {
      target: { value: 'req-1' },
    });
    fireEvent.click(screen.getByTestId('voucher-create'));

    await waitFor(() => expect(create).toHaveBeenCalledTimes(1));
    const payload = create.mock.calls[0][0];
    expect(payload).toMatchObject({
      requisition_id: 'req-1',
      mode: 'DRAFT',
      department_id: 'dep-1',
      issue_date: expect.any(String),
    });
    expect(payload.idempotency_key).toBe(`vale:req-1:${payload.issue_date}`);
    expect(await screen.findByText(/Vale VA-000166 generado/)).toBeInTheDocument();
    expect(screen.getByTestId('voucher-pdf-VA-000166').getAttribute('href')).toContain(
      '/api/v1/documents/vouchers/va-1/pdf',
    );
    expect(screen.getByTestId('voucher-xlsx-VA-000166').getAttribute('href')).toContain(
      '/api/v1/documents/vouchers/va-1/xlsx',
    );
  });

  it('registra nombres de firmas sin generar grafías y consulta el historial', async () => {
    const { sign, renders } = renderVouchers(true);

    expect(await screen.findByTestId('voucher-row-VA-000166')).toBeInTheDocument();
    fireEvent.click(screen.getByTestId('voucher-sign-VA-000166'));
    fireEvent.change(screen.getByTestId('sign-received'), {
      target: { value: 'RECEPCION SINTETICA' },
    });
    fireEvent.change(screen.getByTestId('sign-authorized'), {
      target: { value: 'AUTORIZACION SINTETICA' },
    });
    fireEvent.change(screen.getByTestId('sign-dispatched'), {
      target: { value: 'DESPACHO SINTETICO' },
    });
    fireEvent.click(screen.getByTestId('voucher-sign-save'));

    await waitFor(() => expect(sign).toHaveBeenCalledWith('va-1', {
      received_by_name: 'RECEPCION SINTETICA',
      authorized_by_name: 'AUTORIZACION SINTETICA',
      dispatched_by_name: 'DESPACHO SINTETICO',
    }));
    expect(await screen.findByText(/No se generó ninguna firma gráfica/)).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('voucher-history-VA-000166'));
    expect(await screen.findByTestId('render-PDF-false')).toBeInTheDocument();
    expect(renders).toHaveBeenCalledWith('vouchers', 'va-1');
  });

  it('oculta acciones sensibles cuando el perfil carece de permiso', async () => {
    mockApi(true);
    const limited: User = { ...user, permissions: ['document.render'] };
    render(<AuthProvider initialUser={limited}><Vouchers /></AuthProvider>);

    expect(await screen.findByTestId('voucher-row-VA-000166')).toBeInTheDocument();
    expect(screen.getByTestId('voucher-issue-VA-000166')).toBeDisabled();
    expect(screen.getByTestId('voucher-sign-VA-000166')).toBeDisabled();
    expect(screen.getByTestId('voucher-create')).toBeDisabled();
    expect(screen.getByText('Su perfil no tiene permiso para generar vales.')).toBeInTheDocument();
  });
});
