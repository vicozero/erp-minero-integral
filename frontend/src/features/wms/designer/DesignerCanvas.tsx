import { useRef, useState, type PointerEvent } from 'react';
import { newElement, TYPE_LABELS } from './constants';
import type { DesignerTool, PlanElement } from './types';

export interface DesignerCanvasProps {
  elements: PlanElement[];
  selectedIds: string[];
  width: number;
  height: number;
  gridSize: number;
  showGrid: boolean;
  snapToGrid: boolean;
  zoom: number;
  pan: { x: number; y: number };
  visibleLayers: Record<string, boolean>;
  tool: DesignerTool;
  onSelect: (ids: string[]) => void;
  onChange: (element: PlanElement) => void;
  onCommit: () => void;
  onCreate: (element: PlanElement) => void;
  onPanChange: (pan: { x: number; y: number }) => void;
}

type DragState =
  | { kind: 'element'; startX: number; startY: number; originals: Map<string, PlanElement> }
  | { kind: 'pan'; startX: number; startY: number; origin: { x: number; y: number } }
  | { kind: 'draw'; startX: number; startY: number; currentX: number; currentY: number };

function snap(value: number, grid: number, enabled: boolean): number {
  return enabled ? Math.round(value / grid) * grid : Math.round(value * 100) / 100;
}

function polygonPoints(element: PlanElement): string {
  const custom = element.properties.points;
  if (Array.isArray(custom) && custom.length >= 3) {
    return custom
      .map((point) => {
        const pair = point as [number, number];
        return `${element.x + pair[0] * element.width},${element.y + pair[1] * element.height}`;
      })
      .join(' ');
  }
  const cx = element.width / 2;
  const cy = element.height / 2;
  const rx = element.width / 2;
  const ry = element.height / 2;
  return [
    [0, 0.5],
    [0.25, 0],
    [0.75, 0],
    [1, 0.5],
    [0.75, 1],
    [0.25, 1],
  ]
    .map(([px, py]) => `${element.x + px * (rx * 2)},${element.y + py * (ry * 2)}`)
    .concat(`${element.x + cx},${element.y + cy}`)
    .join(' ');
}

export function DesignerCanvas({
  elements,
  selectedIds,
  width,
  height,
  gridSize,
  showGrid,
  snapToGrid,
  zoom,
  pan,
  visibleLayers,
  tool,
  onSelect,
  onChange,
  onCommit,
  onCreate,
  onPanChange,
}: DesignerCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [guides, setGuides] = useState<{ vertical: number[]; horizontal: number[] }>({
    vertical: [],
    horizontal: [],
  });
  const creationTools = new Set<DesignerTool>([
    'wall', 'door', 'aisle', 'rack', 'shelf', 'position', 'zone', 'receipt',
    'dispatch', 'quarantine', 'office', 'text', 'label', 'rectangle', 'polygon', 'measure',
  ]);

  function scenePoint(event: { clientX: number; clientY: number }): { x: number; y: number } {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: ((event.clientX - rect.left) / rect.width) * width,
      y: ((event.clientY - rect.top) / rect.height) * height,
    };
  }

  function handleBackgroundDown(event: PointerEvent<SVGSVGElement>) {
    if (event.button !== 0 && event.button !== 1) return;
    const point = scenePoint(event);
    if (creationTools.has(tool)) {
      const start = {
        x: snap(point.x, gridSize, snapToGrid),
        y: snap(point.y, gridSize, snapToGrid),
      };
      setDrag({ kind: 'draw', startX: start.x, startY: start.y, currentX: start.x, currentY: start.y });
      event.currentTarget.setPointerCapture(event.pointerId);
      return;
    }
    if (tool === 'move' || event.button === 1) {
      setDrag({ kind: 'pan', startX: event.clientX, startY: event.clientY, origin: pan });
      event.currentTarget.setPointerCapture(event.pointerId);
      return;
    }
    onSelect([]);
  }

  function handleElementDown(event: PointerEvent<SVGGElement>, element: PlanElement) {
    if (tool !== 'select' && tool !== 'move') return;
    event.stopPropagation();
    if (element.locked) return;
    const next = event.shiftKey
      ? selectedIds.includes(element.id)
        ? selectedIds.filter((id) => id !== element.id)
        : [...selectedIds, element.id]
      : selectedIds.includes(element.id)
        ? selectedIds
        : [element.id];
    onSelect(next);
    if (next.includes(element.id)) {
      const originals = new Map<string, PlanElement>();
      next.forEach((id) => {
        const item = elements.find((candidate) => candidate.id === id);
        if (item && !item.locked) originals.set(id, item);
      });
      if (originals.size) {
        setDrag({
          kind: 'element',
          startX: scenePoint(event).x,
          startY: scenePoint(event).y,
          originals,
        });
        event.currentTarget.setPointerCapture(event.pointerId);
      }
    }
  }

  function handleMove(event: PointerEvent<SVGSVGElement>) {
    if (!drag) return;
    if (drag.kind === 'pan') {
      onPanChange({
        x: drag.origin.x + event.clientX - drag.startX,
        y: drag.origin.y + event.clientY - drag.startY,
      });
      return;
    }
    const point = scenePoint(event);
    if (drag.kind === 'draw') {
      setDrag({ ...drag, currentX: point.x, currentY: point.y });
      return;
    }
    const dx = snap(point.x - drag.startX, gridSize, snapToGrid);
    const dy = snap(point.y - drag.startY, gridSize, snapToGrid);
    const vertical: number[] = [];
    const horizontal: number[] = [];
    const first = drag.originals.values().next().value as PlanElement | undefined;
    if (first) {
      const candidatesX = elements
        .filter((item) => !drag.originals.has(item.id))
        .flatMap((item) => [item.x, item.x + item.width / 2, item.x + item.width]);
      const candidatesY = elements
        .filter((item) => !drag.originals.has(item.id))
        .flatMap((item) => [item.y, item.y + item.height / 2, item.y + item.height]);
      const targetX = first.x + dx;
      const targetY = first.y + dy;
      const nearX = candidatesX.find((value) => Math.abs(value - targetX) < gridSize / 2);
      const nearY = candidatesY.find((value) => Math.abs(value - targetY) < gridSize / 2);
      if (nearX !== undefined) vertical.push(nearX);
      if (nearY !== undefined) horizontal.push(nearY);
      setGuides({ vertical, horizontal });
    }
    drag.originals.forEach((original) => {
      const nextX = Math.max(0, Math.min(width - original.width, original.x + dx));
      const nextY = Math.max(0, Math.min(height - original.height, original.y + dy));
      onChange({ ...original, x: nextX, y: nextY });
    });
  }

  function handleUp(event: PointerEvent<SVGSVGElement>) {
    if (!drag) return;
    if (drag.kind === 'draw') {
      const x1 = Math.min(drag.startX, drag.currentX);
      const y1 = Math.min(drag.startY, drag.currentY);
      const x2 = Math.max(drag.startX, drag.currentX);
      const y2 = Math.max(drag.startY, drag.currentY);
      const index = elements.length;
      const element = newElement(tool, snap(x1, gridSize, snapToGrid), snap(y1, gridSize, snapToGrid), index);
      if (element) {
        const drawnWidth = Math.max(x2 - x1, element.width);
        const drawnHeight = Math.max(y2 - y1, element.height);
        const fixedHeight = ['wall', 'door', 'aisle', 'measure', 'text', 'label'].includes(tool);
        onCreate({
          ...element,
          width: snap(drawnWidth, gridSize, false),
          height: fixedHeight ? element.height : snap(drawnHeight, gridSize, false),
        });
      }
    } else if (drag.kind === 'element') {
      onCommit();
      setGuides({ vertical: [], horizontal: [] });
    }
    setDrag(null);
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  }

  const gridLines = showGrid
    ? Array.from({ length: Math.ceil(width / gridSize) + 1 }, (_, index) => index * gridSize)
    : [];
  const gridRows = showGrid
    ? Array.from({ length: Math.ceil(height / gridSize) + 1 }, (_, index) => index * gridSize)
    : [];

  return (
    <div className="designer-canvas-wrap" style={{ transform: `translate(${pan.x}px, ${pan.y}px)` }}>
      <svg
        ref={svgRef}
        className="designer-svg"
        viewBox={`0 0 ${width} ${height}`}
        width={width * zoom}
        height={height * zoom}
        role="application"
        aria-label="Lienzo del diseñador de planos"
        onPointerDown={handleBackgroundDown}
        onPointerMove={handleMove}
        onPointerUp={handleUp}
        onPointerCancel={handleUp}
      >
        <rect x={0} y={0} width={width} height={height} fill="#f8fafc" />
        {gridLines.map((value) => (
          <line key={`vx-${value}`} x1={value} y1={0} x2={value} y2={height} stroke="#e2e8f0" strokeWidth={0.5} />
        ))}
        {gridRows.map((value) => (
          <line key={`hy-${value}`} x1={0} y1={value} x2={width} y2={value} stroke="#e2e8f0" strokeWidth={0.5} />
        ))}
        {guides.vertical.map((value) => (
          <line key={`gv-${value}`} x1={value} y1={0} x2={value} y2={height} stroke="#f43f5e" strokeDasharray="6 4" strokeWidth={1.5} />
        ))}
        {guides.horizontal.map((value) => (
          <line key={`gh-${value}`} x1={0} y1={value} x2={width} y2={value} stroke="#f43f5e" strokeDasharray="6 4" strokeWidth={1.5} />
        ))}
        {elements
          .filter((element) => element.visible && visibleLayers[element.layer] !== false)
          .sort((a, b) => a.z_index - b.z_index)
          .map((element) => {
            const selected = selectedIds.includes(element.id);
            const common = {
              stroke: selected ? '#e11d48' : element.color,
              strokeWidth: selected ? 2.5 : 1.25,
              opacity: element.locked ? 0.55 : 1,
              onPointerDown: (event: PointerEvent<SVGGElement>) => handleElementDown(event, element),
            };
            const label = `${TYPE_LABELS[element.type]} · ${element.name}`;
            return (
              <g key={element.id} data-element-id={element.id} {...common} style={{ cursor: element.locked ? 'not-allowed' : 'move' }}>
                <title>{label}</title>
                {element.type === 'POLYGON' ? (
                  <polygon points={polygonPoints(element)} fill={element.color} fillOpacity={0.22} />
                ) : element.type === 'TEXT' || element.type === 'LABEL' ? (
                  <text
                    x={element.x}
                    y={element.y + element.height}
                    fontSize={Math.max(10, element.height)}
                    fill={element.color}
                  >
                    {element.name}
                  </text>
                ) : element.type === 'MEASUREMENT' ? (
                  <>
                    <line x1={element.x} y1={element.y} x2={element.x + element.width} y2={element.y} stroke={element.color} strokeWidth={2} />
                    <text x={element.x} y={element.y - 4} fontSize={12} fill={element.color}>
                      {`${Math.round(element.width)} u`}
                    </text>
                  </>
                ) : (
                  <rect
                    x={element.x}
                    y={element.y}
                    width={element.width}
                    height={element.height}
                    rx={['RACK', 'SHELF', 'POSITION'].includes(element.type) ? 3 : 0}
                    fill={element.color}
                    fillOpacity={element.type === 'WALL' || element.type === 'DOOR' ? 0.9 : 0.28}
                    transform={element.rotation ? `rotate(${element.rotation} ${element.x + element.width / 2} ${element.y + element.height / 2})` : undefined}
                  />
                )}
                {selected && (
                  <rect
                    x={element.x - 3}
                    y={element.y - 3}
                    width={element.width + 6}
                    height={element.height + 6}
                    fill="none"
                    stroke="#e11d48"
                    strokeDasharray="4 3"
                    strokeWidth={1}
                  />
                )}
              </g>
            );
          })}
        {drag?.kind === 'draw' && (
          <rect
            x={Math.min(drag.startX, drag.currentX)}
            y={Math.min(drag.startY, drag.currentY)}
            width={Math.abs(drag.currentX - drag.startX)}
            height={Math.abs(drag.currentY - drag.startY)}
            fill="#2563eb"
            fillOpacity={0.15}
            stroke="#2563eb"
            strokeDasharray="5 3"
          />
        )}
      </svg>
    </div>
  );
}
