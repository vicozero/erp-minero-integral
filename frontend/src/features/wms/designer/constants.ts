import type { DesignerTool, ElementType, PlanElement } from './types';

export const TOOL_GROUPS: Array<{ label: string; tools: DesignerTool[] }> = [
  { label: 'Navegación', tools: ['select', 'move', 'measure'] },
  {
    label: 'Estructura',
    tools: ['wall', 'door', 'aisle', 'zone', 'rectangle', 'polygon'],
  },
  {
    label: 'Almacenamiento',
    tools: ['rack', 'shelf', 'position'],
  },
  {
    label: 'Áreas',
    tools: ['receipt', 'dispatch', 'quarantine', 'office'],
  },
  { label: 'Anotaciones', tools: ['text', 'label'] },
];

export const TOOL_LABELS: Record<DesignerTool, string> = {
  select: 'Seleccionar',
  move: 'Mover',
  wall: 'Pared',
  door: 'Puerta',
  aisle: 'Pasillo',
  rack: 'Rack',
  shelf: 'Estante',
  position: 'Posición',
  zone: 'Zona de materiales',
  receipt: 'Recepción',
  dispatch: 'Despacho',
  quarantine: 'Cuarentena',
  office: 'Oficina',
  text: 'Texto',
  label: 'Etiqueta',
  rectangle: 'Rectángulo',
  polygon: 'Polígono',
  measure: 'Medir',
};

export const TOOL_ICONS: Record<DesignerTool, string> = {
  select: '⌖',
  move: '✥',
  wall: '▬',
  door: '⌑',
  aisle: '↔',
  rack: '▥',
  shelf: '☰',
  position: '◇',
  zone: '⬚',
  receipt: '⇥',
  dispatch: '⇤',
  quarantine: '⚠',
  office: '⌂',
  text: 'T',
  label: '◫',
  rectangle: '▭',
  polygon: '⬡',
  measure: '⌁',
};

export const TYPE_TO_TOOL: Record<ElementType, DesignerTool> = {
  WALL: 'wall',
  DOOR: 'door',
  AISLE: 'aisle',
  RACK: 'rack',
  SHELF: 'shelf',
  POSITION: 'position',
  ZONE: 'zone',
  RECEIPT: 'receipt',
  DISPATCH: 'dispatch',
  QUARANTINE: 'quarantine',
  OFFICE: 'office',
  TEXT: 'text',
  LABEL: 'label',
  RECTANGLE: 'rectangle',
  POLYGON: 'polygon',
  MEASUREMENT: 'measure',
};

export const TYPE_LABELS: Record<ElementType, string> = {
  WALL: 'Pared',
  DOOR: 'Puerta',
  AISLE: 'Pasillo',
  RACK: 'Rack',
  SHELF: 'Estante',
  POSITION: 'Posición',
  ZONE: 'Zona',
  RECEIPT: 'Recepción',
  DISPATCH: 'Despacho',
  QUARANTINE: 'Cuarentena',
  OFFICE: 'Oficina',
  TEXT: 'Texto',
  LABEL: 'Etiqueta',
  RECTANGLE: 'Rectángulo',
  POLYGON: 'Polígono',
  MEASUREMENT: 'Medida',
};

const DEFAULTS: Partial<Record<DesignerTool, { width: number; height: number; color: string; type: ElementType; layer: string }>> = {
  wall: { width: 200, height: 8, color: '#475569', type: 'WALL', layer: 'estructura' },
  door: { width: 60, height: 8, color: '#f59e0b', type: 'DOOR', layer: 'estructura' },
  aisle: { width: 240, height: 50, color: '#cbd5e1', type: 'AISLE', layer: 'circulación' },
  rack: { width: 180, height: 60, color: '#2563eb', type: 'RACK', layer: 'racks' },
  shelf: { width: 120, height: 40, color: '#0ea5e9', type: 'SHELF', layer: 'racks' },
  position: { width: 30, height: 20, color: '#38bdf8', type: 'POSITION', layer: 'posiciones' },
  zone: { width: 220, height: 140, color: '#a78bfa', type: 'ZONE', layer: 'zonas' },
  receipt: { width: 180, height: 100, color: '#22c55e', type: 'RECEIPT', layer: 'áreas' },
  dispatch: { width: 180, height: 100, color: '#14b8a6', type: 'DISPATCH', layer: 'áreas' },
  quarantine: { width: 180, height: 100, color: '#ef4444', type: 'QUARANTINE', layer: 'áreas' },
  office: { width: 140, height: 100, color: '#f97316', type: 'OFFICE', layer: 'áreas' },
  text: { width: 120, height: 20, color: '#0f172a', type: 'TEXT', layer: 'anotaciones' },
  label: { width: 90, height: 24, color: '#0f172a', type: 'LABEL', layer: 'anotaciones' },
  rectangle: { width: 140, height: 90, color: '#64748b', type: 'RECTANGLE', layer: 'anotaciones' },
  polygon: { width: 100, height: 100, color: '#64748b', type: 'POLYGON', layer: 'anotaciones' },
  measure: { width: 100, height: 2, color: '#e11d48', type: 'MEASUREMENT', layer: 'medidas' },
};

export function newElement(tool: DesignerTool, x: number, y: number, index: number): PlanElement | null {
  const config = DEFAULTS[tool];
  if (!config) return null;
  return {
    id: `${tool}-${Date.now().toString(36)}-${index.toString(36)}`,
    type: config.type,
    name: `${TOOL_LABELS[tool]} ${index + 1}`,
    code: null,
    x,
    y,
    width: config.width,
    height: config.height,
    rotation: 0,
    color: config.color,
    visible: true,
    locked: false,
    layer: config.layer,
    z_index: index,
    dimensions_verified: false,
    wms_location_id: null,
    properties: {},
  };
}

export const LAYER_COLORS: Record<string, string> = {
  estructura: '#475569',
  circulación: '#cbd5e1',
  racks: '#2563eb',
  posiciones: '#38bdf8',
  zonas: '#a78bfa',
  áreas: '#22c55e',
  anotaciones: '#0f172a',
  medidas: '#e11d48',
  default: '#64748b',
};
