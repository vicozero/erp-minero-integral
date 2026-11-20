export type ElementType =
  | 'WALL'
  | 'DOOR'
  | 'AISLE'
  | 'RACK'
  | 'SHELF'
  | 'POSITION'
  | 'ZONE'
  | 'RECEIPT'
  | 'DISPATCH'
  | 'QUARANTINE'
  | 'OFFICE'
  | 'TEXT'
  | 'LABEL'
  | 'RECTANGLE'
  | 'POLYGON'
  | 'MEASUREMENT';

export interface PlanElement {
  id: string;
  type: ElementType;
  name: string;
  code?: string | null;
  x: number;
  y: number;
  width: number;
  height: number;
  depth?: number | null;
  rotation: number;
  color: string;
  visible: boolean;
  locked: boolean;
  layer: string;
  z_index: number;
  dimensions_verified: boolean;
  wms_location_id?: string | null;
  properties: Record<string, unknown>;
}

export interface PlanPayload {
  label: string;
  width: number;
  height: number;
  grid_size: number;
  scale_label: string | null;
  dimensions_verified: boolean;
  elements: PlanElement[];
  revision: number;
  notes: string | null;
}

export interface FloorPlan {
  id: string;
  warehouse_id: string;
  plan_version: number;
  status: 'DRAFT' | 'PUBLISHED' | 'ARCHIVED';
  label: string;
  width: number;
  height: number;
  grid_size: number;
  scale_label: string | null;
  dimensions_verified: boolean;
  elements: PlanElement[];
  location_refs: Array<Record<string, unknown>>;
  revision: number;
  is_active: boolean;
  notes: string | null;
  can_edit: boolean;
  can_publish: boolean;
  created_at: string;
  updated_at: string | null;
  published_at: string | null;
}

export interface FloorPlanWorkspace {
  warehouse_id: string;
  active: FloorPlan | null;
  draft: FloorPlan | null;
  versions: FloorPlan[];
}

export interface RackBlueprint {
  name: string;
  code: string;
  zone: string;
  aisle: string;
  rack: string;
  modules: number;
  levels: number;
  positions_per_level: number;
  width: number;
  depth: number;
  level_height: number;
  orientation: number;
  capacity_per_position: number;
  capacity_validated: boolean;
  location_type: string;
  x: number;
  y: number;
  create_locations: boolean;
}

export interface RackBlueprintResult {
  element: PlanElement;
  locations: Array<Record<string, unknown>>;
  created_count: number;
  total_positions: number;
  warning: string;
}

export interface PlanImportPreview {
  label: string;
  width: number;
  height: number;
  element_count: number;
  linked_location_count: number;
  revision: number;
  warning: string;
}

export type DesignerTool =
  | 'select'
  | 'move'
  | 'wall'
  | 'door'
  | 'aisle'
  | 'rack'
  | 'shelf'
  | 'position'
  | 'zone'
  | 'receipt'
  | 'dispatch'
  | 'quarantine'
  | 'office'
  | 'text'
  | 'label'
  | 'rectangle'
  | 'polygon'
  | 'measure';

export type CameraPreset = 'orbit' | 'top' | 'isometric' | 'front' | 'aisle';

export interface SceneSnapshot {
  elements: PlanElement[];
  label: string;
  width: number;
  height: number;
  gridSize: number;
  scaleLabel: string | null;
  dimensionsVerified: boolean;
  notes: string | null;
}
