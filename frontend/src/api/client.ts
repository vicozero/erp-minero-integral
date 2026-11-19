import type {
  AdminUser,
  ApprovalDecision,
  AuditEntry,
  Availability,
  Catalogs,
  Department,
  HistoryEvent,
  LoginResponse,
  PasswordResetOut,
  Permission,
  PurchaseOrder,
  Requisition,
  RequisitionAttachment,
  RequisitionDraftUpdatePayload,
  RequisitionFilters,
  RequisitionPayload,
  Role,
  Session,
  StockMovement,
  User,
  UserCreatePayload,
  UserCreated,
  UserUpdatePayload,
  FamilyPayload,
  ItemFamily,
  ItemPhoto,
  LocationPayload,
  WmsItem,
  WmsItemDetail,
  WmsLocation,
  WmsLocationDetail,
  WmsSearchFilters,
} from './types';

// En el portal compilado la API está en el mismo origen, detrás del proxy
// inverso. VITE_API_URL solo se usa en configuraciones temporales de
// desarrollo; si está vacío, todas las peticiones son relativas.
const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');
const CSRF_COOKIE = 'erp_csrf';
const SAFE_METHODS = new Set(['GET', 'HEAD', 'OPTIONS']);

// El token CSRF se mantiene solo en memoria; la cookie del navegador se usa
// como respaldo tras recargar la página. Nunca se guarda el token de sesión:
// viaja únicamente en una cookie HttpOnly gestionada por el backend.
let csrfToken: string | null = null;

export function setCsrfToken(value: string | null): void {
  csrfToken = value;
}

export function getCsrfToken(): string | null {
  if (csrfToken) return csrfToken;
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${CSRF_COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = 'ApiError';
  }
}

/** Traduce fallos HTTP a mensajes accionables sin exponer datos sensibles. */
export function describeApiError(cause: unknown, fallback: string): string {
  if (!(cause instanceof ApiError)) {
    return cause instanceof Error ? cause.message : fallback;
  }
  switch (cause.status) {
    case 401:
      return 'La sesión ha caducado. Inicie sesión nuevamente.';
    case 403:
      return `Sin permiso para esta operación. ${cause.message}`.trim();
    case 409:
      return `Conflicto con el estado actual del documento: ${cause.message}`;
    case 422:
      return `Revise los datos capturados: ${cause.message}`;
    default:
      return cause.message || fallback;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase();
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (!SAFE_METHODS.has(method)) {
    const csrf = getCsrfToken();
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });
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
  // --- Sesión ---------------------------------------------------------
  login: (username: string, password: string) =>
    request<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<void>('/api/v1/auth/logout', { method: 'POST' }),
  me: () => request<User>('/api/v1/auth/me'),
  changePassword: (current_password: string, new_password: string) =>
    request<LoginResponse>('/api/v1/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ current_password, new_password }),
    }),
  mySessions: () => request<Session[]>('/api/v1/auth/sessions'),
  revokeSession: (id: string) => request<void>(`/api/v1/auth/sessions/${id}/revoke`, { method: 'POST' }),

  // --- Administración -------------------------------------------------
  users: () => request<AdminUser[]>('/api/v1/admin/users'),
  createUser: (payload: UserCreatePayload) =>
    request<UserCreated>('/api/v1/admin/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateUser: (id: string, payload: UserUpdatePayload) =>
    request<AdminUser>(`/api/v1/admin/users/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deactivateUser: (id: string) => request<AdminUser>(`/api/v1/admin/users/${id}`, { method: 'DELETE' }),
  assignRole: (id: string, role_code: string, scope_type = 'GLOBAL') =>
    request<AdminUser>(`/api/v1/admin/users/${id}/roles`, {
      method: 'POST',
      body: JSON.stringify({ role_code, scope_type }),
    }),
  removeRole: (id: string, role_code: string) =>
    request<AdminUser>(`/api/v1/admin/users/${id}/roles/${role_code}`, { method: 'DELETE' }),
  setDepartments: (id: string, department_ids: string[]) =>
    request<AdminUser>(`/api/v1/admin/users/${id}/departments`, {
      method: 'PUT',
      body: JSON.stringify(department_ids),
    }),
  resetPassword: (id: string, reason?: string) =>
    request<PasswordResetOut>(`/api/v1/admin/users/${id}/reset-password`, {
      method: 'POST',
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  roles: () => request<Role[]>('/api/v1/admin/roles'),
  permissions: () => request<Permission[]>('/api/v1/admin/permissions'),
  adminDepartments: () => request<Department[]>('/api/v1/admin/departments'),
  sessions: () => request<Session[]>('/api/v1/admin/sessions'),

  // --- Operación ------------------------------------------------------
  catalogs: () => request<Catalogs>('/api/v1/catalogs'),
  requisitions: (filters: RequisitionFilters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const query = params.toString();
    return request<Requisition[]>(`/api/v1/requisitions${query ? `?${query}` : ''}`);
  },
  createRequisition: (payload: RequisitionPayload) =>
    request<Requisition>('/api/v1/requisitions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  submitRequisition: (id: string) =>
    request<Requisition>(`/api/v1/requisitions/${id}/submit`, { method: 'POST' }),
  decideRequisition: (id: string, decisions: ApprovalDecision[], reason?: string) =>
    request<Requisition>(`/api/v1/requisitions/${id}/decide`, {
      method: 'POST',
      body: JSON.stringify({ decisions, reason }),
    }),
  updateRequisitionDraft: (id: string, payload: RequisitionDraftUpdatePayload) =>
    request<Requisition>(`/api/v1/requisitions/${id}/draft`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  cancelRequisition: (id: string, reason: string) =>
    request<Requisition>(`/api/v1/requisitions/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  history: (id: string) => request<HistoryEvent[]>(`/api/v1/requisitions/${id}/history`),
  attachments: (id: string) =>
    request<RequisitionAttachment[]>(`/api/v1/requisitions/${id}/attachments`),
  uploadAttachment: (id: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<RequisitionAttachment>(`/api/v1/requisitions/${id}/attachments`, {
      method: 'POST',
      body: form,
    });
  },
  attachmentUrl: (requisitionId: string, attachmentId: string) =>
    `${API_URL}/api/v1/requisitions/${requisitionId}/attachments/${attachmentId}/download`,
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
  expireReservations: () =>
    request<{ released: number }>('/api/v1/inventory/reservations/expire', { method: 'POST' }),
  kardex: () => request<StockMovement[]>('/api/v1/inventory/kardex'),
  purchases: () => request<PurchaseOrder[]>('/api/v1/purchases'),
  createPurchase: (payload: {
    requisition_id: string;
    supplier_id: string;
    warehouse_id: string;
    notes?: string;
    idempotency_key?: string;
  }) =>
    request<PurchaseOrder>('/api/v1/purchases/from-shortages', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  approvePurchase: (id: string) =>
    request<PurchaseOrder>(`/api/v1/purchases/${id}/approve`, { method: 'POST' }),
  cancelPurchase: (id: string, reason: string) =>
    request<PurchaseOrder>(`/api/v1/purchases/${id}/cancel`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
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
  audit: (limit = 100, action?: string) =>
    request<AuditEntry[]>(`/api/v1/audit?limit=${limit}${action ? `&action=${encodeURIComponent(action)}` : ''}`),

  // --- WMS · Lote A -----------------------------------------------------
  wmsFamilies: () => request<ItemFamily[]>('/api/v1/wms/families'),
  createFamily: (payload: FamilyPayload) =>
    request<ItemFamily>('/api/v1/wms/families', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  wmsSearchItems: (filters: WmsSearchFilters = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
    });
    const query = params.toString();
    return request<WmsItem[]>(`/api/v1/wms/items/search${query ? `?${query}` : ''}`);
  },
  wmsItemDetail: (id: string) => request<WmsItemDetail>(`/api/v1/wms/items/${id}`),
  wmsPhotoUrl: (id: string) => `${API_URL}/api/v1/wms/items/${id}/photo`,
  uploadItemPhoto: (id: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return request<ItemPhoto>(`/api/v1/wms/items/${id}/photo`, {
      method: 'POST',
      body: form,
    });
  },
  wmsLocations: (filters: {
    warehouse_id?: string;
    location_type?: string;
    status?: string;
    query?: string;
  } = {}) => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    const query = params.toString();
    return request<WmsLocation[]>(`/api/v1/wms/locations${query ? `?${query}` : ''}`);
  },
  wmsLocationDetail: (id: string) => request<WmsLocationDetail>(`/api/v1/wms/locations/${id}`),
  createLocation: (payload: LocationPayload) =>
    request<WmsLocation>('/api/v1/wms/locations', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};
