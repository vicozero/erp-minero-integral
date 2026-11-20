import { useMemo, useState, type FormEvent } from 'react';
import type { RackBlueprint } from './types';

export interface RackWizardProps {
  x: number;
  y: number;
  canManageLocations: boolean;
  onCancel: () => void;
  onConfirm: (payload: RackBlueprint) => void;
}

const INITIAL: RackBlueprint = {
  name: 'Rack A-01',
  code: 'RACK-A-01',
  zone: 'A',
  aisle: '01',
  rack: '01',
  modules: 4,
  levels: 5,
  positions_per_level: 3,
  width: 360,
  depth: 70,
  level_height: 18,
  orientation: 0,
  capacity_per_position: 0,
  capacity_validated: false,
  location_type: 'STANDARD',
  x: 0,
  y: 0,
  create_locations: false,
};

export function RackWizard({ x, y, canManageLocations, onCancel, onConfirm }: RackWizardProps) {
  const [form, setForm] = useState<RackBlueprint>({
    ...INITIAL,
    x,
    y,
    create_locations: canManageLocations,
  });
  const total = form.modules * form.levels * form.positions_per_level;
  const preview = useMemo(() => {
    const moduleWidth = form.width / Math.max(1, form.modules);
    const slotWidth = moduleWidth / Math.max(1, form.positions_per_level);
    const cells: Array<{ x: number; y: number; width: number; height: number }> = [];
    for (let module = 0; module < form.modules; module += 1) {
      for (let level = 0; level < form.levels; level += 1) {
        for (let slot = 0; slot < form.positions_per_level; slot += 1) {
          cells.push({
            x: module * moduleWidth + slot * slotWidth,
            y: level * form.level_height,
            width: slotWidth,
            height: form.level_height,
          });
        }
      }
    }
    return cells;
  }, [form]);

  function submit(event: FormEvent) {
    event.preventDefault();
    onConfirm({
      ...form,
      code: form.code.trim().toUpperCase(),
      zone: form.zone.trim().toUpperCase(),
      aisle: form.aisle.trim().toUpperCase(),
      rack: form.rack.trim().toUpperCase(),
      create_locations: form.create_locations && canManageLocations,
    });
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onCancel}>
      <form
        className="modal-card rack-wizard"
        role="dialog"
        aria-modal="true"
        aria-label="Asistente para crear rack"
        onMouseDown={(event) => event.stopPropagation()}
        onSubmit={submit}
      >
        <header className="modal-head">
          <h2>Asistente de rack</h2>
          <button type="button" className="icon-button" onClick={onCancel} aria-label="Cerrar asistente">✕</button>
        </header>
        <div className="rack-wizard-body">
          <fieldset className="rack-wizard-form">
            <legend>Configuración</legend>
            <label>Nombre<input value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} required minLength={2} /></label>
            <label>Código<input value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} required pattern="[A-Za-z0-9][A-Za-z0-9_\-.]*" /></label>
            <div className="field-row">
              <label>Zona<input value={form.zone} onChange={(event) => setForm({ ...form, zone: event.target.value })} required /></label>
              <label>Pasillo<input value={form.aisle} onChange={(event) => setForm({ ...form, aisle: event.target.value })} required /></label>
              <label>Rack<input value={form.rack} onChange={(event) => setForm({ ...form, rack: event.target.value })} required /></label>
            </div>
            <div className="field-row">
              <label>Módulos<input type="number" min={1} max={50} value={form.modules} onChange={(event) => setForm({ ...form, modules: Number(event.target.value) })} /></label>
              <label>Niveles<input type="number" min={1} max={20} value={form.levels} onChange={(event) => setForm({ ...form, levels: Number(event.target.value) })} /></label>
              <label>Posiciones/nivel<input type="number" min={1} max={20} value={form.positions_per_level} onChange={(event) => setForm({ ...form, positions_per_level: Number(event.target.value) })} /></label>
            </div>
            <div className="field-row">
              <label>Ancho<input type="number" min={1} value={form.width} onChange={(event) => setForm({ ...form, width: Number(event.target.value) })} /></label>
              <label>Profundidad<input type="number" min={1} value={form.depth} onChange={(event) => setForm({ ...form, depth: Number(event.target.value) })} /></label>
              <label>Altura/nivel<input type="number" min={1} value={form.level_height} onChange={(event) => setForm({ ...form, level_height: Number(event.target.value) })} /></label>
            </div>
            <div className="field-row">
              <label>Orientación
                <select value={form.orientation} onChange={(event) => setForm({ ...form, orientation: Number(event.target.value) })}>
                  <option value={0}>0°</option><option value={90}>90°</option><option value={180}>180°</option><option value={270}>270°</option>
                </select>
              </label>
              <label>Tipo
                <select value={form.location_type} onChange={(event) => setForm({ ...form, location_type: event.target.value })}>
                  <option value="STANDARD">Estándar</option>
                  <option value="RECEIPT">Recepción</option>
                  <option value="QUARANTINE">Cuarentena</option>
                  <option value="DISPATCH">Despacho</option>
                </select>
              </label>
            </div>
            <div className="field-row">
              <label>Capacidad por posición<input type="number" min={0} step="any" value={form.capacity_per_position} onChange={(event) => setForm({ ...form, capacity_per_position: Number(event.target.value) })} /></label>
              <label className="checkbox-line">
                <input type="checkbox" checked={form.capacity_validated} onChange={(event) => setForm({ ...form, capacity_validated: event.target.checked })} />
                Capacidad validada
              </label>
            </div>
            <div className="field-row">
              <label>X<input type="number" min={0} step="any" value={form.x} onChange={(event) => setForm({ ...form, x: Number(event.target.value) })} /></label>
              <label>Y<input type="number" min={0} step="any" value={form.y} onChange={(event) => setForm({ ...form, y: Number(event.target.value) })} /></label>
            </div>
            <label className="checkbox-line">
              <input
                type="checkbox"
                checked={form.create_locations && canManageLocations}
                disabled={!canManageLocations}
                onChange={(event) => setForm({ ...form, create_locations: event.target.checked })}
              />
              Crear/vincular ubicaciones WMS
            </label>
            {!canManageLocations && <p className="hint">Su perfil puede dibujar el rack, pero no crear ubicaciones WMS.</p>}
          </fieldset>
          <section className="rack-wizard-preview" aria-label="Previsualización del rack">
            <h3>Previsualización 2D</h3>
            <svg
              viewBox={`0 0 ${form.width} ${Math.max(30, form.levels * form.level_height)}`}
              className="rack-preview-svg"
              role="img"
              aria-label={`${total} posiciones potenciales`}
            >
              {preview.map((cell, index) => (
                <rect key={index} x={cell.x} y={cell.y} width={cell.width} height={cell.height} fill="#38bdf8" fillOpacity={0.25} stroke="#0284c7" strokeWidth={0.8} />
              ))}
            </svg>
            <h3>Previsualización 3D referencial</h3>
            <div className="rack-preview-3d" aria-hidden="true">
              {Array.from({ length: form.levels }, (_, level) => (
                <div key={level} className="rack-preview-level" style={{ width: `${Math.min(100, form.modules * 14)}%` }}>
                  {Array.from({ length: form.modules }, (_, module) => (
                    <span key={module} />
                  ))}
                </div>
              ))}
            </div>
            <p className="hint">
              {form.modules} módulos × {form.levels} niveles × {form.positions_per_level} posiciones = <strong>{total}</strong> posiciones potenciales.
              {' '}Geometría referencial; no modifica existencias.
            </p>
          </section>
        </div>
        <footer className="modal-foot">
          <button type="button" className="button button-ghost" onClick={onCancel}>Cancelar</button>
          <button type="submit" className="button button-primary" disabled={total > 500}>Crear rack</button>
        </footer>
      </form>
    </div>
  );
}
