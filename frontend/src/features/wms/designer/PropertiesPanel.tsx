import type { LocationInventory, WmsLocation } from '../../../api/types';
import { formatNumber } from '../../../components/ui';
import { TYPE_LABELS } from './constants';
import type { PlanElement } from './types';

export interface PropertiesPanelProps {
  selected: PlanElement[];
  locations: WmsLocation[];
  inventory: LocationInventory | null;
  canViewCost: boolean;
  onChange: (element: PlanElement) => void;
  onDelete: () => void;
  onDuplicate: () => void;
  onRotate: () => void;
}

function numberValue(value: unknown): string {
  return String(value ?? '');
}

export function PropertiesPanel({
  selected,
  locations,
  inventory,
  canViewCost,
  onChange,
  onDelete,
  onDuplicate,
  onRotate,
}: PropertiesPanelProps) {
  if (selected.length === 0) {
    return (
      <aside className="designer-panel" aria-label="Propiedades del objeto">
        <div className="designer-panel-head"><strong>Propiedades</strong></div>
        <p className="hint">Seleccione un objeto del plano para editar sus propiedades.</p>
      </aside>
    );
  }
  if (selected.length > 1) {
    return (
      <aside className="designer-panel" aria-label="Propiedades de la selección">
        <div className="designer-panel-head"><strong>{selected.length} objetos seleccionados</strong></div>
        <p className="hint">Use las acciones de alineación y distribución de la barra de herramientas. El borrado aplica a toda la selección.</p>
        <button type="button" className="button button-danger button-small" onClick={onDelete}>Eliminar selección</button>
      </aside>
    );
  }
  const element = selected[0];
  const patch = (changes: Partial<PlanElement>) => onChange({ ...element, ...changes });

  return (
    <aside className="designer-panel" aria-label="Propiedades del objeto">
      <div className="designer-panel-head">
        <strong>Propiedades</strong>
        <span className="badge">{TYPE_LABELS[element.type]}</span>
      </div>
      <div className="designer-panel-body">
        <label>Nombre<input value={element.name} onChange={(event) => patch({ name: event.target.value })} maxLength={120} /></label>
        <label>Código<input value={numberValue(element.code)} onChange={(event) => patch({ code: event.target.value || null })} maxLength={80} /></label>
        <div className="field-row">
          <label>X<input type="number" step="any" value={element.x} onChange={(event) => patch({ x: Number(event.target.value) })} /></label>
          <label>Y<input type="number" step="any" value={element.y} onChange={(event) => patch({ y: Number(event.target.value) })} /></label>
        </div>
        <div className="field-row">
          <label>Ancho<input type="number" min={1} step="any" value={element.width} onChange={(event) => patch({ width: Number(event.target.value) })} /></label>
          <label>Largo<input type="number" min={1} step="any" value={element.height} onChange={(event) => patch({ height: Number(event.target.value) })} /></label>
        </div>
        <div className="field-row">
          <label>Altura<input type="number" min={1} step="any" value={numberValue(element.depth)} onChange={(event) => patch({ depth: event.target.value ? Number(event.target.value) : null })} /></label>
          <label>Rotación<input type="number" min={-360} max={360} value={element.rotation} onChange={(event) => patch({ rotation: Number(event.target.value) })} /></label>
        </div>
        <label>Color<input type="color" value={element.color} onChange={(event) => patch({ color: event.target.value })} /></label>
        <label>Capa<select value={element.layer} onChange={(event) => patch({ layer: event.target.value })}>
          {Array.from(new Set(['default', 'estructura', 'circulación', 'racks', 'posiciones', 'zonas', 'áreas', 'anotaciones', 'medidas', element.layer])).map((layer) => (
            <option key={layer} value={layer}>{layer}</option>
          ))}
        </select></label>
        <label>Estado<select value={element.locked ? 'BLOCKED' : 'ACTIVE'} onChange={(event) => patch({ locked: event.target.value === 'BLOCKED' })}>
          <option value="ACTIVE">Activo</option>
          <option value="BLOCKED">Bloqueado</option>
        </select></label>
        <label className="checkbox-line">
          <input type="checkbox" checked={element.dimensions_verified} onChange={(event) => patch({ dimensions_verified: event.target.checked })} />
          Dimensiones verificadas
        </label>
        <p className="hint">Si no hay validación documental, deje la casilla sin marcar: la geometría se trata como referencial.</p>
        <label>Ubicación WMS vinculada
          <select
            value={element.wms_location_id ?? ''}
            onChange={(event) => patch({ wms_location_id: event.target.value || null })}
          >
            <option value="">Sin vincular</option>
            {locations.map((location) => (
              <option key={location.id} value={location.id}>{location.code}</option>
            ))}
          </select>
        </label>
        <div className="designer-actions-row">
          <button type="button" className="button button-ghost button-small" onClick={onRotate}>Rotar 15°</button>
          <button type="button" className="button button-ghost button-small" onClick={onDuplicate}>Duplicar</button>
          <button type="button" className="button button-danger button-small" onClick={onDelete}>Eliminar</button>
        </div>
        {inventory && (
          <section className="wms-detail" aria-label="Datos WMS reales de la ubicación">
            <h3>Datos WMS · {inventory.code}</h3>
            <p className="hint">{inventory.hierarchy_path}</p>
            <dl className="detail-grid">
              <div><dt>Existencias</dt><dd>{formatNumber(inventory.occupied_qty)}</dd></div>
              <div><dt>Disponible</dt><dd>{formatNumber(inventory.items.reduce((sum, row) => sum + Number(row.available_qty), 0))}</dd></div>
              <div><dt>Reservada</dt><dd>{formatNumber(inventory.items.reduce((sum, row) => sum + Number(row.reserved_qty), 0))}</dd></div>
            </dl>
            {inventory.items.length === 0 ? (
              <p className="hint">Sin artículos registrados en esta ubicación.</p>
            ) : (
              <ul className="inventory-list">
                {inventory.items.map((item) => (
                  <li key={item.item_id}>
                    <strong>{item.code}</strong> · {item.description}
                    <div className="hint">{item.manufacturer_part_no ? `Parte ${item.manufacturer_part_no} · ` : ''}{item.uom_code}</div>
                    <div>
                      Física {formatNumber(item.on_hand_qty)} · Disp. {formatNumber(item.available_qty)} · Res. {formatNumber(item.reserved_qty)}
                      {canViewCost && item.unit_cost !== null && ` · Costo ${formatNumber(item.unit_cost)}`}
                    </div>
                    {item.last_movement && (
                      <div className="hint">Último movimiento: {item.last_movement.movement_no} · {item.last_movement.movement_type}</div>
                    )}
                  </li>
                ))}
              </ul>
            )}
            {inventory.restrictions.length > 0 && (
              <p className="hint">Restricciones: {inventory.restrictions.map((row) => row.item_family_name ?? row.item_code ?? 'Regla').join(', ')}</p>
            )}
            {!canViewCost && <p className="hint">El costo se omite: su perfil no tiene autorización para consultarlo.</p>}
          </section>
        )}
      </div>
    </aside>
  );
}
