export interface User {
  id: string;
  username: string;
  email: string;
  full_name: string;
  status: string;
  roles: string[];
  permissions: string[];
  department_ids: string[];
  must_change_password: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  csrf_token: string;
  expires_at: string;
  must_change_password: boolean;
  user: User;
}

export interface Session {
  id: string;
  user_id: string;
  created_at: string;
  expires_at: string;
  last_seen_at: string | null;
  revoked_at: string | null;
}

export interface AdminUser extends User {
  failed_login_attempts: number;
  locked_until: string | null;
  last_login_at: string | null;
  created_at: string;
}

export interface UserCreated extends AdminUser {
  temporary_password: string | null;
}

export interface Role {
  code: string;
  name: string;
  description: string | null;
}

export interface Permission {
  code: string;
  description: string | null;
}

export interface Department {
  id: string;
  code: string;
  name: string | null;
  mining_unit_id: string | null;
}

export interface PasswordResetOut {
  username: string;
  temporary_password: string;
  must_change_password: boolean;
  detail: string;
}

export interface CatalogItem {
  id: string;
  code: string | null;
  name: string | null;
}

export interface Catalogs {
  mining_units: CatalogItem[];
  departments: CatalogItem[];
  warehouses: CatalogItem[];
  items: CatalogItem[];
  uoms: CatalogItem[];
  suppliers: CatalogItem[];
  cost_centers: CatalogItem[];
  equipment: CatalogItem[];
}

/** Colores derivados en backend; no son estados administrativos. */
export type SlaColor = 'GREEN' | 'YELLOW' | 'RED' | 'NONE';

export interface SlaResult {
  color: SlaColor;
  label: string;
  measured: boolean;
  administrative_status: string;
  base_at: string | null;
  elapsed_hours: string | null;
  green_deadline: string | null;
  yellow_deadline: string | null;
  policy_id: string | null;
  policy_scope: string;
  emergency_active: boolean;
  message: string | null;
}

export interface SlaEvaluation {
  id: string;
  requisition_id: string;
  occurred_at: string;
  base_at: string | null;
  elapsed_hours: string | null;
  color: SlaColor;
  label: string;
  policy_id: string | null;
  policy_scope: string;
  trigger: string;
  actor_id: string | null;
  metadata_json: Record<string, unknown> | null;
}

export interface RequisitionLine {
  id: string;
  line_no: number;
  item_id: string | null;
  description: string;
  uom_id: string;
  requested_qty: string;
  authorised_qty: string;
  cancelled_qty: string;
  status: string;
  notes: string | null;
  reserved_qty: string;
  purchased_qty: string;
  received_qty: string;
  delivered_qty: string;
  pending_qty: string;
}

export interface Requisition {
  id: string;
  document_no: string;
  department_id: string;
  warehouse_id: string | null;
  equipment_id: string | null;
  cost_center_id: string;
  requisition_type: string;
  priority: string;
  status: string;
  justification: string;
  observations: string | null;
  needed_at: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  work_order_no: string | null;
  created_at: string;
  /** Indicador calculado por el backend; nunca sustituye a `status`. */
  sla?: SlaResult | null;
  lines: RequisitionLine[];
}

export interface RequisitionAttachment {
  id: string;
  requisition_id: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
}

/** Vale de almacén derivado de entregas; nunca genera movimientos al imprimirse. */
export interface VoucherLine {
  id: string;
  line_no: number;
  requisition_line_id: string | null;
  stock_movement_id: string | null;
  item_id: string | null;
  item_code: string;
  uom_code: string;
  description: string;
  requested_qty: string;
  dispatched_qty: string;
}

export interface Voucher {
  id: string;
  document_no: string;
  department_id: string;
  warehouse_id: string | null;
  source_requisition_id: string | null;
  cost_center_code: string | null;
  area: string | null;
  usage_equipment: string | null;
  issue_date: string;
  status: 'DRAFT' | 'ISSUED';
  template_code: string;
  template_version: number;
  issued_at: string | null;
  created_at: string;
  received_by_name: string | null;
  authorized_by_name: string | null;
  dispatched_by_name: string | null;
  signatures_recorded_at: string | null;
  lines: VoucherLine[];
}

export interface VoucherCreatePayload {
  department_id: string;
  warehouse_id?: string | null;
  requisition_id?: string | null;
  mode?: 'DRAFT' | 'DELIVERY';
  cost_center_code?: string | null;
  area?: string | null;
  usage_equipment?: string | null;
  issue_date?: string | null;
  lines?: Array<{
    item_id?: string | null;
    item_code: string;
    uom_code: string;
    description: string;
    requested_qty: string;
    dispatched_qty?: string;
  }>;
  idempotency_key?: string | null;
}

export interface VoucherSignaturePayload {
  received_by_name?: string | null;
  authorized_by_name?: string | null;
  dispatched_by_name?: string | null;
}

export interface RenderRecord {
  id: string;
  document_no: string;
  document_format: 'PDF' | 'XLSX';
  sha256: string;
  size_bytes: number;
  is_reprint: boolean;
  rendered_at: string;
  source_render_id: string | null;
}

/** Fila del tablero SLA; el color es calculado y no es un estado administrativo. */
export interface SlaRequisition {
  id: string;
  document_no: string;
  department_id: string;
  equipment_id: string | null;
  requester_id: string | null;
  department_name: string | null;
  department_code: string | null;
  equipment: string | null;
  responsible: string | null;
  status: string;
  administrative_status: string;
  priority: string;
  requisition_type: string;
  submitted_at: string | null;
  needed_at: string | null;
  pending_days: string | null;
  fulfillment_percent: string;
  sla: SlaResult;
}

export interface SlaFilters {
  sla_color?: SlaColor;
  status?: string;
  priority?: string;
  department_id?: string;
  equipment_id?: string;
  requester_id?: string;
  date_from?: string;
  date_to?: string;
}

export interface TraceStage {
  stage: string;
  label: string;
  completed: boolean;
  document_no: string | null;
  occurred_at: string | null;
  detail: string | null;
}

export interface RequisitionTrace {
  requisition_id: string;
  document_no: string;
  administrative_status: string;
  tracking: {
    sla: SlaResult | null;
    administrative_status: string | null;
    pending_days: string | null;
    fulfillment_percent: string;
    needed_at: string | null;
  };
  stages: TraceStage[];
  approvals: Array<Record<string, unknown> & { decision?: string; decided_by?: string | null }>;
  reservations: Array<Record<string, unknown> & { reservation_no?: string; quantity?: string }>;
  deliveries: Array<Record<string, unknown> & { movement_no?: string; quantity?: string }>;
  vouchers: Array<Record<string, unknown> & { document_no?: string; status?: string }>;
  document_events: Array<Record<string, unknown> & { event_type?: string }>;
  audit_events: Array<Record<string, unknown> & { action?: string }>;
  generated_at: string;
}

export interface RequisitionFilters {
  status?: string;
  sla_color?: SlaColor;
  priority?: string;
  department_id?: string;
  equipment_id?: string;
  document_no?: string;
  date_from?: string;
  date_to?: string;
}

export interface Availability {
  item_id: string;
  item_code: string;
  warehouse_id: string;
  warehouse_code: string;
  on_hand_qty: string;
  reserved_qty: string;
  available_qty: string;
}

export interface StockMovement {
  id: string;
  movement_no: string;
  movement_type: string;
  direction: string;
  quantity: string;
  item_id: string;
  warehouse_id: string;
  balance_after_qty: string;
  requisition_line_id: string | null;
  source_document_type: string;
  posted_at: string;
}

export interface PurchaseOrderLine {
  id: string;
  line_no: number;
  requisition_line_id: string;
  item_id: string;
  ordered_qty: string;
  received_qty: string;
  cancelled_qty: string;
  unit_price: string;
}

export interface PurchaseOrder {
  id: string;
  document_no: string;
  requisition_id: string;
  supplier_id: string;
  warehouse_id: string;
  status: string;
  lines: PurchaseOrderLine[];
}

export interface HistoryEvent {
  event_type: string;
  from_status: string | null;
  to_status: string | null;
  occurred_at: string;
  actor_id: string | null;
  metadata: Record<string, unknown> | null;
}

export interface AuditEntry {
  id: string;
  occurred_at: string;
  actor_username: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  detail: string | null;
  request_id: string;
}

export interface RequisitionPayload {
  department_id: string;
  warehouse_id?: string | null;
  equipment_id?: string | null;
  cost_center_id: string;
  requisition_type: 'STOCK' | 'PURCHASE' | 'SERVICE';
  priority: 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';
  justification: string;
  observations?: string | null;
  needed_at?: string | null;
  work_order_no?: string | null;
  lines: Array<{
    id?: string;
    item_id?: string | null;
    description: string;
    uom_id: string;
    requested_qty: string;
    notes?: string | null;
  }>;
}

/** Campos aceptados por PATCH /requisitions/{id}/draft (el resto se ignora). */
export interface RequisitionDraftUpdatePayload {
  justification: string;
  priority?: 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';
  observations?: string | null;
  needed_at?: string | null;
  work_order_no?: string | null;
  lines: Array<{
    id?: string;
    item_id?: string | null;
    description: string;
    uom_id: string;
    requested_qty: string;
    notes?: string | null;
  }>;
}

export interface ApprovalDecision {
  requisition_line_id: string;
  decision: 'APPROVE' | 'REJECT';
  approved_qty?: string;
  reason?: string;
}

export interface UserCreatePayload {
  username: string;
  email: string;
  full_name: string;
  password?: string;
  roles: string[];
  department_ids: string[];
}

export interface UserUpdatePayload {
  email?: string;
  full_name?: string;
  status?: 'ACTIVE' | 'INACTIVE';
  department_ids?: string[];
}

// --- WMS · Lote A: catálogo, ubicaciones y búsquedas -----------------------
export interface ItemFamily {
  id: string;
  code: string;
  name: string;
  parent_id: string | null;
  is_active: boolean;
}

export interface WmsItem {
  id: string;
  code: string;
  description: string;
  family_id: string | null;
  family_name: string | null;
  manufacturer: string | null;
  manufacturer_part_no: string | null;
  barcode: string | null;
  uom_id: string;
  uom_code: string;
  standard_cost: string;
  lot_tracked: boolean;
  serial_tracked: boolean;
  is_consumable: boolean;
  is_returnable: boolean;
  is_tool: boolean;
  is_active: boolean;
  on_hand_qty: string;
  reserved_qty: string;
  available_qty: string;
  location_count: number;
}

export interface StockLocationBalance {
  location_id: string;
  location_code: string;
  warehouse_code: string;
  zone: string | null;
  aisle: string | null;
  lot_number: string | null;
  on_hand_qty: string;
  reserved_qty: string;
  available_qty: string;
}

export interface WmsLot {
  id: string;
  lot_number: string;
  status: string;
  manufactured_at: string | null;
  expiry_date: string | null;
}

export interface WmsSerial {
  id: string;
  serial_number: string;
  status: string;
  lot_id: string | null;
  current_location_id: string | null;
}

export interface ItemCrossReference {
  id: string;
  reference_type: string;
  reference_code: string;
  equivalent_item_id: string | null;
  authorised: boolean;
}

export interface ItemSupplierInfo {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_part_number: string | null;
  lead_time_days: number;
  min_order_qty: string;
  preferred: boolean;
  last_unit_cost: string | null;
  currency: string;
}

export interface RelatedDocument {
  document_no: string;
  document_type: string;
  status: string;
  occurred_at: string;
}

export interface WmsItemDetail extends WmsItem {
  image_url: string | null;
  supplier_name: string | null;
  default_supplier_id: string | null;
  reorder_point: string | null;
  safety_stock: string | null;
  max_stock: string | null;
  weight_kg: string | null;
  volume_m3: string | null;
  storage_temperature_min: string | null;
  storage_temperature_max: string | null;
  locations: StockLocationBalance[];
  lots: WmsLot[];
  serials: WmsSerial[];
  cross_references: ItemCrossReference[];
  suppliers: ItemSupplierInfo[];
  movements: StockMovement[];
  related_documents: RelatedDocument[];
}

export interface WmsLocation {
  id: string;
  warehouse_id: string;
  warehouse_code: string;
  code: string;
  parent_id: string | null;
  zone: string | null;
  aisle: string | null;
  rack: string | null;
  level: string | null;
  position: string | null;
  location_type: string;
  qr_token: string;
  capacity_qty: string;
  status: string;
  is_pickable: boolean;
  is_receivable: boolean;
  coord_x: string | null;
  coord_y: string | null;
  /** Jerarquía derivada en backend: unidad / almacén / zona / pasillo / ... */
  hierarchy_path: string;
  occupied_qty: string;
  item_count: number;
}

export interface LocationMapNode {
  id: string;
  code: string;
  parent_id: string | null;
  hierarchy_path: string;
  zone: string | null;
  aisle: string | null;
  rack: string | null;
  level: string | null;
  position: string | null;
  location_type: string;
  status: string;
  coord_x: string | null;
  coord_y: string | null;
  occupied_qty: string;
  item_count: number;
}

export interface LocationMapVersion {
  id: string;
  warehouse_id: string;
  map_version: number;
  label: string;
  background_url: string | null;
  background_name: string | null;
  background_sha256: string | null;
  /** Siempre false: ninguna imagen se presenta como plano exacto. */
  is_exact: boolean;
  width: string;
  height: string;
  is_active: boolean;
  notes: string | null;
}

export interface LocationMap extends LocationMapVersion {
  nodes: LocationMapNode[];
}

export interface LocationMapMetadataPayload {
  label: string;
  width: string;
  height: string;
  notes?: string | null;
}

export interface LocationCoordinatesOut {
  id: string;
  coord_x: string;
  coord_y: string;
  version: number;
}

export interface LocationQr {
  location_id: string;
  qr_token: string;
  svg_url: string;
  lookup_url: string;
}

export interface LocationLookup {
  id: string;
  warehouse_id: string;
  warehouse_code: string;
  code: string;
  hierarchy_path: string;
  location_type: string;
  status: string;
  coord_x: string | null;
  coord_y: string | null;
  qr_token: string;
}

export interface LocationRestriction {
  item_family_id: string | null;
  item_id: string | null;
  max_qty: string | null;
  allows_lot_mix: boolean;
  allows_serial_mix: boolean;
}

export interface WmsLocationDetail extends WmsLocation {
  restrictions: LocationRestriction[];
  items: StockLocationBalance[];
}

export interface LocationPayload {
  warehouse_id: string;
  code: string;
  parent_id?: string | null;
  zone?: string | null;
  aisle?: string | null;
  rack?: string | null;
  level?: string | null;
  position?: string | null;
  coord_x?: string | null;
  coord_y?: string | null;
  location_type: 'RECEIPT' | 'STANDARD' | 'QUARANTINE' | 'DISPATCH' | 'TRANSIT' | 'SCRAP';
  capacity_qty: string;
  status?: 'ACTIVE' | 'BLOCKED' | 'INACTIVE';
  is_pickable?: boolean;
  is_receivable?: boolean;
}

export interface FamilyPayload {
  code: string;
  name: string;
  parent_id?: string | null;
  is_active?: boolean;
}

export interface ItemPhoto {
  item_id: string;
  image_path: string;
  image_sha256: string;
  image_url: string;
}

export interface WmsSearchFilters {
  query?: string;
  family_id?: string;
  warehouse_id?: string;
  location_id?: string;
  equipment_id?: string;
  active_only?: boolean;
  limit?: number;
  offset?: number;
}
