import type {
  AuditEntry,
  Availability,
  Catalogs,
  HistoryEvent,
  PurchaseOrder,
  Requisition,
  RequisitionPayload,
  StockMovement,
  User,
} from './types';

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000';

let token: string | null = null;

export function setToken(value: string | null): void {
  token = value;
}

export function getToken(): string | null {
  return token;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Content-Type', 'application/json');
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) {
    let detail = `Error ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // Respuesta sin cuerpo JSON.
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  me: () => request<User>('/api/v1/auth/me'),
  catalogs: () => request<Catalogs>('/api/v1/catalogs'),
  requisitions: () => request<Requisition[]>('/api/v1/requisitions'),
  createRequisition: (payload: RequisitionPayload) =>
    request<Requisition>('/api/v1/requisitions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  submitRequisition: (id: string) =>
    request<Requisition>(`/api/v1/requisitions/${id}/submit`, { method: 'POST' }),
  decideRequisition: (
    id: string,
    decisions: Array<{
      requisition_line_id: string;
      decision: 'APPROVE' | 'REJECT';
      approved_qty?: string;
      reason?: string;
    }>,
    reason?: string,
  ) =>
    request<Requisition>(`/api/v1/requisitions/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decisions, reason }),
    }),
  history: (id: string) => request<HistoryEvent[]>(`/api/v1/requisitions/${id}/history`),
  availability: (itemId: string, warehouseId: string) =>
    request<Availability>(
      `/api/v1/inventory/availability?item_id=${itemId}&warehouse_id=${warehouseId}`,
    ),
  reserve: (payload: {
    requisition_line_id: string;
    quantity: string;
    idempotency_key: string;
  }) =>
    request<{ id: string; reservation_no: string; status: string }>('/api/v1/inventory/reservations', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  issue: (payload: {
    requisition_line_id: string;
    quantity: string;
    reservation_id?: string;
    idempotency_key: string;
  }) =>
    request<StockMovement>('/api/v1/inventory/issues', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  kardex: () => request<StockMovement[]>('/api/v1/inventory/kardex'),
  purchases: () => request<PurchaseOrder[]>('/api/v1/purchases'),
  createPurchase: (payload: {
    requisition_id: string;
    supplier_id: string;
    warehouse_id: string;
    notes?: string;
  }) =>
    request<PurchaseOrder>('/api/v1/purchases/from-shortages', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  approvePurchase: (id: string) =>
    request<PurchaseOrder>(`/api/v1/purchases/${id}/approve`, { method: 'POST' }),
  receivePurchase: (
    id: string,
    payload: {
      lines: Array<{ purchase_order_line_id: string; quantity: string }>;
      idempotency_key: string;
    },
  ) =>
    request<{ id: string; document_no: string }>(`/api/v1/purchases/${id}/receive`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  audit: () => request<AuditEntry[]>('/api/v1/audit?limit=100'),
};
