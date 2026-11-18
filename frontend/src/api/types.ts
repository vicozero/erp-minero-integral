export interface User {
  id: string;
  username: string;
  full_name: string;
  roles: string[];
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
  created_at: string;
  lines: RequisitionLine[];
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
  lines: Array<{
    item_id?: string | null;
    description: string;
    uom_id: string;
    requested_qty: string;
    notes?: string | null;
  }>;
}
