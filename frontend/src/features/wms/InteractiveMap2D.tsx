import { useMemo, useRef, useState, type PointerEvent, type WheelEvent } from 'react';
import type { LocationMapNode } from '../../api/types';
import { Icon } from '../../components/Icon';
import { formatNumber } from '../../components/ui';

export type OccupancyTone = 'empty' | 'low' | 'medium' | 'high' | 'blocked';

export const OCCUPANCY_LEGEND: Array<{ tone: OccupancyTone; label: string }> = [
  { tone: 'empty', label: 'Vacía · 0 %' },
  { tone: 'low', label: 'Disponible · 1–69 %' },
  { tone: 'medium', label: 'Ocupación media · 70–89 %' },
  { tone: 'high', label: 'Alta ocupación · 90–100 %' },
  { tone: 'blocked', label: 'Bloqueada' },
];

export function occupancyTone(node: Pick<LocationMapNode, 'status' | 'capacity_qty' | 'occupied_qty'>): OccupancyTone {
  if (node.status === 'BLOCKED') return 'blocked';
  const capacity = Number(node.capacity_qty);
  const occupied = Number(node.occupied_qty);
  if (!Number.isFinite(capacity) || capacity <= 0) return occupied > 0 ? 'low' : 'empty';
  const ratio = occupied / capacity;
  if (ratio <= 0) return 'empty';
  if (ratio < 0.7) return 'low';
  if (ratio < 0.9) return 'medium';
  return 'high';
}

export interface InteractiveMap2DProps {
  nodes: LocationMapNode[];
  width: string;
  height: string;
  label: string;
  backgroundUrl?: string | null;
  selectedId: string | null;
  highlightIds: string[];
  onSelect: (locationId: string) => void;
}

/** Vista superior interactiva. No modifica existencias: sólo proyecta nodos WMS. */
export function InteractiveMap2D({
  nodes,
  width,
  height,
  label,
  backgroundUrl,
  selectedId,
  highlightIds,
  onSelect,
}: InteractiveMap2DProps) {
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const drag = useRef<{ x: number; y: number; ox: number; oy: number } | null>(null);

  const drawn = useMemo(
    () => nodes.filter((node) => node.coord_x !== null && node.coord_y !== null),
    [nodes],
  );
  const widthNumber = Number(width) || 1000;
  const heightNumber = Number(height) || 600;

  function onWheel(event: WheelEvent<HTMLDivElement>) {
    event.preventDefault();
    setZoom((current) => Math.min(3, Math.max(0.5, current + (event.deltaY < 0 ? 0.1 : -0.1))));
  }

  function onPointerDown(event: PointerEvent<HTMLDivElement>) {
    if ((event.target as HTMLElement).closest('button')) return;
    drag.current = { x: event.clientX, y: event.clientY, ox: offset.x, oy: offset.y };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current) return;
    const start = drag.current;
    setOffset({
      x: start.ox + event.clientX - start.x,
      y: start.oy + event.clientY - start.y,
    });
  }

  function onPointerUp(event: PointerEvent<HTMLDivElement>) {
    drag.current = null;
    event.currentTarget.releasePointerCapture?.(event.pointerId);
  }

  function resetView() {
    setZoom(1);
    setOffset({ x: 0, y: 0 });
  }

  return (
    <div className="interactive-map" data-testid="mapa-2d">
      <div className="map-toolbar" role="toolbar" aria-label="Controles del plano 2D">
        <button type="button" className="icon-button" onClick={() => setZoom((z) => Math.min(3, z + 0.2))} aria-label="Acercar plano">+</button>
        <button type="button" className="icon-button" onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))} aria-label="Alejar plano">−</button>
        <button type="button" className="button button-ghost button-small" onClick={resetView}>
          <Icon name="location" size={14} /> Restablecer
        </button>
        <span className="hint">{Math.round(zoom * 100)} %</span>
      </div>

      <div
        className="map-viewport"
        onWheel={onWheel}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        aria-label="Plano superior del almacén"
      >
        <div
          className="map-world"
          style={{
            aspectRatio: `${widthNumber} / ${heightNumber}`,
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
          }}
        >
          {backgroundUrl && (
            <img className="warehouse-map-background" src={backgroundUrl} alt="Fondo referencial del almacén" />
          )}
          <div className="warehouse-map-grid" aria-hidden="true" />
          {drawn.map((node) => {
            const tone = occupancyTone(node);
            const classes = [
              'map-node',
              `map-node-${node.location_type.toLowerCase()}`,
              `map-tone-${tone}`,
              selectedId === node.id ? 'map-node-selected' : '',
              highlightIds.includes(node.id) ? 'map-node-highlight' : '',
            ]
              .filter(Boolean)
              .join(' ');
            return (
              <button
                key={node.id}
                type="button"
                data-location-id={node.id}
                className={classes}
                style={{
                  left: `${Math.min(100, Math.max(0, (Number(node.coord_x) / widthNumber) * 100))}%`,
                  top: `${Math.min(100, Math.max(0, (Number(node.coord_y) / heightNumber) * 100))}%`,
                }}
                title={`${node.hierarchy_path} · ${OCCUPANCY_LEGEND.find((item) => item.tone === tone)?.label}`}
                aria-label={`Ubicación ${node.code}, ${OCCUPANCY_LEGEND.find((item) => item.tone === tone)?.label}`}
                onClick={() => onSelect(node.id)}
              >
                <span>{node.code}</span>
                <small>{formatNumber(node.occupied_qty)}</small>
              </button>
            );
          })}
        </div>
      </div>

      <p className="map-disclaimer" role="note">
        <Icon name="alert" size={14} /> {label}. Geometría y posiciones referenciales; no sustituyen la verificación física.
      </p>

      <div className="map-legend" aria-label="Leyenda de ocupación">
        {OCCUPANCY_LEGEND.map((item) => (
          <span key={item.tone} className="legend-item">
            <i className={`legend-swatch map-tone-${item.tone}`} aria-hidden="true" /> {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
