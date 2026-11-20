import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent } from 'react';
import { api, ApiError, describeApiError } from '../../../api/client';
import type { LocationInventory, LocationMap, WmsLocation } from '../../../api/types';
import { LoadingState } from '../../../components/ui';
import { SceneErrorBoundary } from '../SceneErrorBoundary';
import { DesignerCanvas } from './DesignerCanvas';
import { TOOL_GROUPS, TOOL_ICONS, TOOL_LABELS } from './constants';
import { PropertiesPanel } from './PropertiesPanel';
import { RackWizard } from './RackWizard';
import type {
  CameraPreset,
  DesignerTool,
  FloorPlan,
  FloorPlanWorkspace,
  PlanElement,
  PlanImportPreview,
  PlanPayload,
  SceneSnapshot,
} from './types';
import './designer.css';

const Designer3D = lazy(() => import('./Designer3D'));

export interface DesignerProps {
  warehouseId: string;
  warehouseLabel: string;
  canEdit: boolean;
  canPublish: boolean;
  canManageLocations: boolean;
  canViewCost: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

type Mode = 'consulta' | 'diseno' | 'operacion';

const cloneScene = (scene: SceneSnapshot): SceneSnapshot => ({
  ...scene,
  elements: scene.elements.map((element) => ({ ...element, properties: { ...element.properties } })),
});

function snapshot(plan: FloorPlan): SceneSnapshot {
  return {
    elements: (plan.elements ?? []).map((element) => ({ ...element, properties: { ...element.properties } })),
    label: plan.label,
    width: Number(plan.width),
    height: Number(plan.height),
    gridSize: Number(plan.grid_size) || 20,
    scaleLabel: plan.scale_label,
    dimensionsVerified: plan.dimensions_verified,
    notes: plan.notes,
  };
}

export function Designer({
  warehouseId,
  warehouseLabel,
  canEdit,
  canPublish,
  canManageLocations,
  canViewCost,
  onClose,
  onSaved,
}: DesignerProps) {
  const [workspace, setWorkspace] = useState<FloorPlanWorkspace | null>(null);
  const [scene, setScene] = useState<SceneSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [tool, setTool] = useState<DesignerTool>('select');
  const [mode, setMode] = useState<Mode>('diseno');
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [showGrid, setShowGrid] = useState(true);
  const [snapToGrid, setSnapToGrid] = useState(true);
  const [zoom, setZoom] = useState(0.8);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [visibleLayers, setVisibleLayers] = useState<Record<string, boolean>>({});
  const [view, setView] = useState<'2d' | '3d'>('2d');
  const [showWalls, setShowWalls] = useState(true);
  const [cameraPreset, setCameraPreset] = useState<CameraPreset>('isometric');
  const [resetToken, setResetToken] = useState(0);
  const [dark, setDark] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [wizardOpen, setWizardOpen] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [locations, setLocations] = useState<WmsLocation[]>([]);
  const [inventory, setInventory] = useState<LocationInventory | null>(null);
  const [backgroundUrl, setBackgroundUrl] = useState<string | null>(null);
  const [importState, setImportState] = useState<{ preview: PlanImportPreview; payload: PlanPayload } | null>(null);
  const [historyState, setHistoryState] = useState<{ items: SceneSnapshot[]; index: number }>({ items: [], index: -1 });
  // Durante un arrastre el canvas emite onChange y después onCommit en el mismo
  // ciclo: el closure de `scene` aún es el anterior, por eso se guarda en un ref.
  const sceneRef = useRef<SceneSnapshot | null>(null);
  const clipboard = useRef<PlanElement[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const backgroundInput = useRef<HTMLInputElement>(null);
  const wizardAnchor = useRef({ x: 20, y: 20 });

  const draft = workspace?.draft ?? null;
  const active = workspace?.active ?? null;
  const editable = canEdit && mode !== 'consulta' && draft !== null;
  const readOnlyPlan = draft ?? active;

  useEffect(() => {
    sceneRef.current = scene;
  }, [scene]);

  useEffect(() => {
    let activeRequest = true;
    setLoading(true);
    void (async () => {
      try {
        let next = await api.wmsPlanWorkspace(warehouseId);
        if (!next.draft && canEdit) {
          const created = await api.wmsPlanEnsureDraft(warehouseId);
          next = { ...next, draft: created };
        }
        if (!activeRequest) return;
        setWorkspace(next);
        const initial = next.draft ?? next.active;
        if (initial) {
          const copy = snapshot(initial);
          setScene(copy);
          setHistoryState({ items: [cloneScene(copy)], index: 0 });
        }
        const [map, wmsLocations] = await Promise.all([
          api.wmsLocationMap(warehouseId).catch(() => null),
          api.wmsLocations({ warehouse_id: warehouseId }).catch(() => []),
        ]);
        if (!activeRequest) return;
        setBackgroundUrl(map?.background_url ?? null);
        setLocations(wmsLocations);
      } catch (exc) {
        if (activeRequest) setError(describeApiError(exc, 'No se pudo cargar el plano.'));
      } finally {
        if (activeRequest) setLoading(false);
      }
    })();
    return () => {
      activeRequest = false;
    };
  }, [warehouseId, canEdit]);

  const commit = useCallback((next: SceneSnapshot) => {
    setHistoryState((previous) => {
      const items = [...previous.items.slice(0, previous.index + 1), cloneScene(next)].slice(-50);
      return { items, index: items.length - 1 };
    });
  }, []);

  function replaceScene(next: SceneSnapshot, shouldCommit = true) {
    setScene(next);
    if (shouldCommit) commit(next);
  }

  const undo = useCallback(() => {
    setHistoryState((previous) => {
      if (previous.index <= 0) return previous;
      const index = previous.index - 1;
      setScene(cloneScene(previous.items[index]));
      return { ...previous, index };
    });
  }, []);

  const redo = useCallback(() => {
    setHistoryState((previous) => {
      if (previous.index >= previous.items.length - 1) return previous;
      const index = previous.index + 1;
      setScene(cloneScene(previous.items[index]));
      return { ...previous, index };
    });
  }, []);

  const selected = useMemo(
    () => (scene?.elements ?? []).filter((element) => selectedIds.includes(element.id)),
    [scene, selectedIds],
  );

  useEffect(() => {
    const linked = selected.length === 1 ? selected[0].wms_location_id : null;
    if (!linked) {
      setInventory(null);
      return;
    }
    let active = true;
    api
      .wmsLocationInventory(linked)
      .then((result) => {
        if (active) setInventory(result);
      })
      .catch(() => {
        if (active) setInventory(null);
      });
    return () => {
      active = false;
    };
  }, [selected]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return;
      const modifier = event.ctrlKey || event.metaKey;
      if (modifier && event.key.toLowerCase() === 'z') {
        event.preventDefault();
        if (event.shiftKey) redo();
        else undo();
      } else if (modifier && event.key.toLowerCase() === 'y') {
        event.preventDefault();
        redo();
      } else if (modifier && event.key.toLowerCase() === 'd') {
        event.preventDefault();
        duplicate();
      } else if (modifier && event.key.toLowerCase() === 'c') {
        clipboard.current = cloneScene(scene ?? { elements: [], label: '', width: 0, height: 0, gridSize: 20, scaleLabel: null, dimensionsVerified: false, notes: null }).elements.filter((element) => selectedIds.includes(element.id));
      } else if (modifier && event.key.toLowerCase() === 'v') {
        event.preventDefault();
        paste();
      } else if (event.key === 'Delete' && selectedIds.length && editable) {
        event.preventDefault();
        setConfirmDelete(true);
      } else if (event.key.toLowerCase() === 'r' && editable && selectedIds.length) {
        rotateSelection();
      } else if (event.key === 'Escape') {
        setWizardOpen(false);
        setConfirmDelete(false);
        setImportState(null);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  function updateElement(element: PlanElement, shouldCommit = true) {
    if (!scene || !editable) return;
    replaceScene({ ...scene, elements: scene.elements.map((item) => (item.id === element.id ? element : item)) }, shouldCommit);
  }

  function addElement(element: PlanElement) {
    if (!scene || !editable) return;
    replaceScene({ ...scene, elements: [...scene.elements, element] });
    setSelectedIds([element.id]);
  }

  function deleteSelection() {
    if (!scene || !editable) return;
    replaceScene({ ...scene, elements: scene.elements.filter((element) => !selectedIds.includes(element.id)) });
    setSelectedIds([]);
    setConfirmDelete(false);
  }

  function duplicate() {
    if (!scene || !editable || selectedIds.length === 0) return;
    const copies = scene.elements
      .filter((element) => selectedIds.includes(element.id))
      .map((element, index) => ({
        ...element,
        id: `${element.id}-copy-${Date.now().toString(36)}-${index}`,
        x: Math.min(scene.width - element.width, element.x + scene.gridSize),
        y: Math.min(scene.height - element.height, element.y + scene.gridSize),
        wms_location_id: null,
        properties: { ...element.properties },
      }));
    replaceScene({ ...scene, elements: [...scene.elements, ...copies] });
    setSelectedIds(copies.map((element) => element.id));
  }

  function paste() {
    if (!scene || !editable || clipboard.current.length === 0) return;
    const copies = clipboard.current.map((element, index) => ({
      ...element,
      id: `${element.id}-paste-${Date.now().toString(36)}-${index}`,
      x: Math.min(scene.width - element.width, element.x + scene.gridSize),
      y: Math.min(scene.height - element.height, element.y + scene.gridSize),
      wms_location_id: null,
      properties: { ...element.properties },
    }));
    replaceScene({ ...scene, elements: [...scene.elements, ...copies] });
    setSelectedIds(copies.map((element) => element.id));
  }

  function rotateSelection() {
    if (!scene || !editable) return;
    replaceScene({
      ...scene,
      elements: scene.elements.map((element) =>
        selectedIds.includes(element.id) ? { ...element, rotation: (element.rotation + 15) % 360 } : element,
      ),
    });
  }

  function align(mode: 'left' | 'right' | 'top' | 'bottom' | 'center-x' | 'center-y') {
    if (!scene || !editable || selected.length < 2) return;
    const minX = Math.min(...selected.map((element) => element.x));
    const maxX = Math.max(...selected.map((element) => element.x + element.width));
    const minY = Math.min(...selected.map((element) => element.y));
    const maxY = Math.max(...selected.map((element) => element.y + element.height));
    replaceScene({
      ...scene,
      elements: scene.elements.map((element) => {
        if (!selectedIds.includes(element.id)) return element;
        switch (mode) {
          case 'left': return { ...element, x: minX };
          case 'right': return { ...element, x: maxX - element.width };
          case 'top': return { ...element, y: minY };
          case 'bottom': return { ...element, y: maxY - element.height };
          case 'center-x': return { ...element, x: (minX + maxX) / 2 - element.width / 2 };
          case 'center-y': return { ...element, y: (minY + maxY) / 2 - element.height / 2 };
        }
      }),
    });
  }

  function distribute(axis: 'x' | 'y') {
    if (!scene || !editable || selected.length < 3) return;
    const ordered = [...selected].sort((a, b) => (axis === 'x' ? a.x - b.x : a.y - b.y));
    const first = ordered[0];
    const last = ordered[ordered.length - 1];
    const span = axis === 'x' ? last.x - first.x : last.y - first.y;
    const step = span / (ordered.length - 1);
    const positions = ordered.map((_, index) => (axis === 'x' ? first.x + index * step : first.y + index * step));
    replaceScene({
      ...scene,
      elements: scene.elements.map((element) => {
        const index = ordered.findIndex((item) => item.id === element.id);
        return index < 0 ? element : axis === 'x' ? { ...element, x: positions[index] } : { ...element, y: positions[index] };
      }),
    });
  }

  function payload(): PlanPayload | null {
    if (!scene || !draft) return null;
    return {
      label: scene.label,
      width: scene.width,
      height: scene.height,
      grid_size: scene.gridSize,
      scale_label: scene.scaleLabel,
      dimensions_verified: scene.dimensionsVerified,
      elements: scene.elements,
      revision: draft.revision,
      notes: scene.notes,
    };
  }

  async function save() {
    const body = payload();
    if (!body || !draft) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.wmsPlanSave(draft.id, warehouseId, body);
      setWorkspace((current) => (current ? { ...current, draft: saved } : current));
      setNotice(`Borrador guardado en revisión ${saved.revision}.`);
      onSaved?.();
    } catch (exc) {
      setError(describeApiError(exc, 'No se pudo guardar el borrador.'));
    } finally {
      setSaving(false);
    }
  }

  async function publish() {
    const body = payload();
    if (!body || !draft) return;
    setSaving(true);
    setError(null);
    try {
      const next = await api.wmsPlanPublish(draft.id, warehouseId, body.revision, body.notes ?? undefined);
      setWorkspace(next);
      if (next.draft) {
        const copy = snapshot(next.draft);
        setScene(copy);
        setHistoryState({ items: [cloneScene(copy)], index: 0 });
      }
      setSelectedIds([]);
      setNotice(`Versión ${next.active?.plan_version ?? ''} publicada. La edición continúa en un borrador nuevo.`);
      onSaved?.();
    } catch (exc) {
      setError(describeApiError(exc, 'No se pudo publicar el plano.'));
    } finally {
      setSaving(false);
    }
  }

  async function createRack(blueprint: Parameters<typeof api.wmsPlanCreateRack>[2]) {
    if (!draft || !scene) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.wmsPlanCreateRack(draft.id, warehouseId, blueprint);
      const next = await api.wmsPlanWorkspace(warehouseId);
      setWorkspace(next);
      if (next.draft) {
        const copy = snapshot(next.draft);
        setScene(copy);
        setHistoryState({ items: [...historyState.items.slice(0, historyState.index + 1), cloneScene(copy)].slice(-50), index: Math.min(historyState.index + 1, 49) });
        const rack = copy.elements.find((element) => element.id === result.element.id);
        if (rack) setSelectedIds([rack.id]);
      }
      setWizardOpen(false);
      setNotice(`${result.total_positions} posiciones potenciales · ${result.created_count} ubicaciones WMS creadas. ${result.warning}`);
      onSaved?.();
    } catch (exc) {
      setError(describeApiError(exc, 'No se pudo crear el rack.'));
    } finally {
      setSaving(false);
    }
  }

  async function handleImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const parsed: unknown = JSON.parse(await file.text());
      if (typeof parsed !== 'object' || parsed === null) throw new Error('El archivo no contiene un objeto JSON.');
      const candidate = parsed as Partial<PlanPayload>;
      const body: PlanPayload = {
        label: String(candidate.label ?? 'Plano importado'),
        width: Number(candidate.width ?? scene?.width ?? 1000),
        height: Number(candidate.height ?? scene?.height ?? 600),
        grid_size: Number(candidate.grid_size ?? scene?.gridSize ?? 20),
        scale_label: candidate.scale_label ?? null,
        dimensions_verified: false,
        elements: Array.isArray(candidate.elements) ? (candidate.elements as PlanElement[]) : [],
        revision: draft?.revision ?? 1,
        notes: typeof candidate.notes === 'string' ? candidate.notes : null,
      };
      if (body.elements.length === 0) throw new Error('El JSON no contiene elementos de plano.');
      const preview = await api.wmsPlanImportPreview(body);
      setImportState({ preview, payload: body });
    } catch (exc) {
      setError(exc instanceof ApiError ? exc.message : exc instanceof Error ? exc.message : 'El JSON no es válido.');
    }
  }

  async function applyImport() {
    if (!importState || !draft) return;
    try {
      const saved = await api.wmsPlanSave(draft.id, warehouseId, importState.payload);
      setWorkspace((current) => (current ? { ...current, draft: saved } : current));
      const copy = snapshot(saved);
      setScene(copy);
      commit(copy);
      setImportState(null);
      setNotice(`Importación aplicada: ${copy.elements.length} elementos. No se ejecutaron scripts.`);
      onSaved?.();
    } catch (exc) {
      setError(describeApiError(exc, 'No se pudo aplicar la importación.'));
    }
  }

  function download(filename: string, content: string, type: string) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function exportJson() {
    if (!draft) return;
    try {
      const data = await api.wmsPlanExport(draft.id, warehouseId);
      download(`plano-${warehouseId}.json`, JSON.stringify(data, null, 2), 'application/json');
    } catch (exc) {
      setError(describeApiError(exc, 'No se pudo exportar el JSON.'));
    }
  }

  function svgDataUrl(): Promise<string> {
    const svg = document.querySelector('.designer-svg');
    if (!(svg instanceof SVGSVGElement)) return Promise.reject(new Error('No hay lienzo para exportar.'));
    const copy = svg.cloneNode(true) as SVGSVGElement;
    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    const source = new XMLSerializer().serializeToString(copy);
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = Number(copy.getAttribute('width')) || 1000;
        canvas.height = Number(copy.getAttribute('height')) || 600;
        const context = canvas.getContext('2d');
        if (!context) {
          reject(new Error('No se pudo crear la imagen.'));
          return;
        }
        context.drawImage(image, 0, 0);
        resolve(canvas.toDataURL('image/png'));
      };
      image.onerror = () => reject(new Error('No se pudo convertir el lienzo a PNG.'));
      image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(source)}`;
    });
  }

  async function exportPng() {
    try {
      const url = await svgDataUrl();
      const link = document.createElement('a');
      link.href = url;
      link.download = `plano-${warehouseId}.png`;
      link.click();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'No se pudo exportar el PNG.');
    }
  }

  async function exportPdf() {
    try {
      const url = await svgDataUrl();
      const win = window.open('', '_blank');
      if (!win) {
        setError('El navegador bloqueó la ventana de impresión. Permita ventanas emergentes e intente de nuevo.');
        return;
      }
      win.document.write(`<html><head><title>Plano ${warehouseLabel}</title></head><body style="margin:0"><img src="${url}" style="width:100%" /><script>window.onload=()=>window.print()<\/script></body></html>`);
      win.document.close();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'No se pudo generar el PDF.');
    }
  }

  async function uploadBackground(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const map: LocationMap = await api.wmsLocationMap(warehouseId);
      await api.uploadLocationMapBackground(warehouseId, {
        label: map.label,
        width: String(map.width),
        height: String(map.height),
        notes: map.notes ?? undefined,
      }, file);
      const refreshed = await api.wmsLocationMap(warehouseId);
      setBackgroundUrl(refreshed.background_url ?? null);
      setNotice('Fondo actualizado con los controles existentes (PNG, JPG o WEBP).');
    } catch (exc) {
      setError(describeApiError(exc, 'No se pudo actualizar el fondo.'));
    }
  }

  const layers = useMemo(() => {
    const values = new Set<string>();
    (scene?.elements ?? []).forEach((element) => values.add(element.layer));
    return Array.from(values).sort();
  }, [scene]);

  if (loading || !scene || !readOnlyPlan) {
    return (
      <div className="modal-backdrop">
        <div className="modal-card designer-loading" role="status">
          <h2>Diseñador de planos</h2>
          <LoadingState rows={6} label="Preparando lienzo, ubicaciones WMS e historial…" />
          {error && <p className="error-text">{error}</p>}
          <button type="button" className="button button-ghost" onClick={onClose}>Cerrar</button>
        </div>
      </div>
    );
  }

  return (
    <div className={`modal-backdrop designer-backdrop ${fullscreen ? 'is-fullscreen' : ''} ${dark ? 'designer-dark' : ''}`}>
      <div className="modal-card designer-shell" role="dialog" aria-modal="true" aria-label="Diseñador profesional de planos">
        <header className="designer-header">
          <div>
            <h2>Diseñador de plano · {warehouseLabel}</h2>
            <p className="hint">
              {draft ? `Borrador v${draft.plan_version} · revisión ${draft.revision}` : 'Sólo lectura'} · Geometría referencial, no plano exacto
            </p>
          </div>
          <div className="designer-header-actions">
            <div className="view-switch" role="group" aria-label="Modo de trabajo">
              {(['consulta', 'diseno', 'operacion'] as Mode[]).map((value) => (
                <button
                  key={value}
                  type="button"
                  className={mode === value ? 'button button-primary button-small' : 'button button-ghost button-small'}
                  onClick={() => setMode(value)}
                >
                  {value === 'diseno' ? 'Diseño' : value === 'consulta' ? 'Consulta' : 'Operación'}
                </button>
              ))}
            </div>
            <button type="button" className="icon-button" onClick={() => setDark((value) => !value)} aria-label="Cambiar tema claro u oscuro" title="Claro / oscuro">◐</button>
            <button type="button" className="icon-button" onClick={() => setFullscreen((value) => !value)} aria-label="Pantalla completa" title="Pantalla completa">⛶</button>
            <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar diseñador">✕</button>
          </div>
        </header>

        {error && <p className="error-text" role="alert">{error}</p>}
        {notice && <p className="hint designer-notice" role="status">{notice}</p>}

        <div className="designer-toolbar" role="toolbar" aria-label="Herramientas del diseñador">
          {TOOL_GROUPS.map((group) => (
            <div key={group.label} className="tool-group">
              <span className="tool-group-label">{group.label}</span>
              {group.tools.map((item) => (
                <button
                  key={item}
                  type="button"
                  className={`tool-button ${tool === item ? 'is-active' : ''}`}
                  onClick={() => setTool(item)}
                  disabled={!editable}
                  title={TOOL_LABELS[item]}
                  aria-label={TOOL_LABELS[item]}
                >
                  <span aria-hidden="true">{TOOL_ICONS[item]}</span>
                </button>
              ))}
            </div>
          ))}
          <div className="tool-group">
            <span className="tool-group-label">Edición</span>
            <button type="button" className="tool-button" onClick={undo} disabled={historyState.index <= 0} title="Deshacer" aria-label="Deshacer">↶</button>
            <button type="button" className="tool-button" onClick={redo} disabled={historyState.index >= historyState.items.length - 1} title="Rehacer" aria-label="Rehacer">↷</button>
            <button type="button" className="tool-button" onClick={duplicate} disabled={!editable || !selectedIds.length} title="Duplicar" aria-label="Duplicar">⧉</button>
            <button type="button" className="tool-button" onClick={() => setConfirmDelete(true)} disabled={!editable || !selectedIds.length} title="Eliminar" aria-label="Eliminar">⌫</button>
            <button type="button" className="tool-button" onClick={rotateSelection} disabled={!editable || !selectedIds.length} title="Rotar 15°" aria-label="Rotar">↻</button>
          </div>
          <div className="tool-group">
            <span className="tool-group-label">Alineación</span>
            <button type="button" className="tool-button" onClick={() => align('left')} disabled={!editable || selected.length < 2} title="Alinear a la izquierda">⇤</button>
            <button type="button" className="tool-button" onClick={() => align('right')} disabled={!editable || selected.length < 2} title="Alinear a la derecha">⇥</button>
            <button type="button" className="tool-button" onClick={() => align('top')} disabled={!editable || selected.length < 2} title="Alinear arriba">⇡</button>
            <button type="button" className="tool-button" onClick={() => align('bottom')} disabled={!editable || selected.length < 2} title="Alinear abajo">⇣</button>
            <button type="button" className="tool-button" onClick={() => distribute('x')} disabled={!editable || selected.length < 3} title="Distribuir horizontalmente">⟷</button>
            <button type="button" className="tool-button" onClick={() => distribute('y')} disabled={!editable || selected.length < 3} title="Distribuir verticalmente">⟵⟶</button>
          </div>
        </div>

        <div className="designer-subtoolbar" role="toolbar" aria-label="Controles de lienzo y archivo">
          <label className="checkbox-line"><input type="checkbox" checked={showGrid} onChange={(event) => setShowGrid(event.target.checked)} /> Cuadrícula</label>
          <label className="checkbox-line"><input type="checkbox" checked={snapToGrid} onChange={(event) => setSnapToGrid(event.target.checked)} /> Ajuste magnético</label>
          <label>Cuadrícula
            <input
              type="number"
              min={5}
              max={200}
              value={scene.gridSize}
              disabled={!editable}
              onChange={(event) => replaceScene({ ...scene, gridSize: Number(event.target.value) || 20 })}
            />
          </label>
          <label>Zoom
            <input type="range" min={0.3} max={2} step={0.1} value={zoom} onChange={(event) => setZoom(Number(event.target.value))} aria-label="Zoom del lienzo" />
          </label>
          <button type="button" className="button button-ghost button-small" onClick={() => { setZoom(0.8); setPan({ x: 0, y: 0 }); }}>Centrar</button>
          <div className="view-switch" role="group" aria-label="Vista 2D o 3D">
            <button type="button" className={view === '2d' ? 'button button-primary button-small' : 'button button-ghost button-small'} onClick={() => setView('2d')}>2D</button>
            <button type="button" className={view === '3d' ? 'button button-primary button-small' : 'button button-ghost button-small'} onClick={() => setView('3d')}>3D</button>
          </div>
          {view === '3d' && (
            <>
              <label className="checkbox-line"><input type="checkbox" checked={showWalls} onChange={(event) => setShowWalls(event.target.checked)} /> Paredes</label>
              <select value={cameraPreset} onChange={(event) => setCameraPreset(event.target.value as CameraPreset)} aria-label="Vista de cámara">
                <option value="orbit">Orbital</option><option value="top">Superior</option><option value="isometric">Isométrica</option><option value="front">Frontal</option><option value="aisle">Por pasillo</option>
              </select>
              <button type="button" className="button button-ghost button-small" onClick={() => setResetToken((value) => value + 1)}>Restablecer cámara</button>
            </>
          )}
          <span className="toolbar-spacer" />
          <button type="button" className="button button-ghost button-small" onClick={() => backgroundInput.current?.click()} disabled={!canManageLocations}>Fondo</button>
          <button type="button" className="button button-ghost button-small" onClick={() => fileInput.current?.click()} disabled={!editable}>Importar JSON</button>
          <button type="button" className="button button-ghost button-small" onClick={() => void exportJson()}>Exportar JSON</button>
          <button type="button" className="button button-ghost button-small" onClick={() => void exportPng()}>PNG</button>
          <button type="button" className="button button-ghost button-small" onClick={() => void exportPdf()}>PDF</button>
          <input ref={fileInput} type="file" accept="application/json,.json" hidden onChange={(event) => void handleImport(event)} />
          <input ref={backgroundInput} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(event) => void uploadBackground(event)} />
        </div>

        <div className="designer-main">
          <aside className="designer-left" aria-label="Capas y asistente">
            <div className="designer-panel-head"><strong>Capas</strong></div>
            <ul className="layer-list">
              {layers.map((layer) => (
                <li key={layer}>
                  <label className="checkbox-line">
                    <input
                      type="checkbox"
                      checked={visibleLayers[layer] !== false}
                      onChange={(event) => setVisibleLayers({ ...visibleLayers, [layer]: event.target.checked })}
                    />
                    {layer || 'default'}
                  </label>
                  <span>{scene.elements.filter((element) => element.layer === layer).length}</span>
                </li>
              ))}
            </ul>
            <button type="button" className="button button-secondary button-small" disabled={!editable} onClick={() => {
              const rect = document.querySelector('.designer-canvas-wrap')?.getBoundingClientRect();
              wizardAnchor.current = {
                x: Math.max(0, (rect?.width ?? 800) / 4 / zoom),
                y: Math.max(0, (rect?.height ?? 600) / 4 / zoom),
              };
              setWizardOpen(true);
            }}>
              Asistente de rack
            </button>
            <div className="designer-legend">
              <p className="hint">Mayús + clic: selección múltiple</p>
              <p className="hint">Herramienta Mover: arrastrar fondo</p>
              <p className="hint">Ctrl+Z / Ctrl+Y · Ctrl+C / Ctrl+V · Supr</p>
            </div>
          </aside>

          <section className="designer-stage" aria-label="Área de diseño">
            <div className="designer-meta">
              <label>Título<input value={scene.label} disabled={!editable} onChange={(event) => replaceScene({ ...scene, label: event.target.value }, false)} onBlur={() => commit(scene)} /></label>
              <label>Escala<input value={scene.scaleLabel ?? ''} disabled={!editable} placeholder="Referencial" onChange={(event) => replaceScene({ ...scene, scaleLabel: event.target.value || null }, false)} onBlur={() => commit(scene)} /></label>
              <label>Ancho<input type="number" min={1} disabled={!editable} value={scene.width} onChange={(event) => replaceScene({ ...scene, width: Number(event.target.value) }, false)} onBlur={() => commit(scene)} /></label>
              <label>Alto<input type="number" min={1} disabled={!editable} value={scene.height} onChange={(event) => replaceScene({ ...scene, height: Number(event.target.value) }, false)} onBlur={() => commit(scene)} /></label>
              <label className="checkbox-line"><input type="checkbox" checked={scene.dimensionsVerified} disabled={!editable} onChange={(event) => replaceScene({ ...scene, dimensionsVerified: event.target.checked })} /> Dimensiones verificadas</label>
            </div>
            <div className="designer-viewport" onWheel={(event) => {
              if (!event.ctrlKey) return;
              event.preventDefault();
              setZoom((current) => Math.max(0.3, Math.min(2, current + (event.deltaY < 0 ? 0.1 : -0.1))));
            }}>
              {view === '2d' ? (
                <>
                  {backgroundUrl && (
                    <img className="designer-background" src={backgroundUrl} alt="Fondo referencial del almacén" />
                  )}
                  <DesignerCanvas
                    elements={scene.elements}
                    selectedIds={selectedIds}
                    width={scene.width}
                    height={scene.height}
                    gridSize={scene.gridSize}
                    showGrid={showGrid}
                    snapToGrid={snapToGrid}
                    zoom={zoom}
                    pan={pan}
                    visibleLayers={visibleLayers}
                    tool={editable ? tool : 'select'}
                    onSelect={setSelectedIds}
                    onChange={(element) => {
                      if (!scene) return;
                      setScene({ ...scene, elements: scene.elements.map((item) => (item.id === element.id ? element : item)) });
                    }}
                    onCommit={() => sceneRef.current && commit(sceneRef.current)}
                    onCreate={addElement}
                    onPanChange={setPan}
                  />
                </>
              ) : (
                <SceneErrorBoundary onFallback={() => setView('2d')}>
                  <Suspense fallback={<LoadingState rows={4} label="Preparando vista 3D…" />}>
                    <Designer3D
                      elements={scene.elements}
                      width={scene.width}
                      height={scene.height}
                      selectedIds={selectedIds}
                      showWalls={showWalls}
                      cameraPreset={cameraPreset}
                      resetToken={resetToken}
                      onSelect={setSelectedIds}
                    />
                  </Suspense>
                </SceneErrorBoundary>
              )}
            </div>
            {workspace?.versions.length ? (
              <details className="designer-history">
                <summary>Historial de versiones publicadas ({workspace.versions.length})</summary>
                <ul>
                  {workspace.versions.map((version) => (
                    <li key={version.id}>
                      v{version.plan_version} · {new Date(version.published_at ?? version.created_at).toLocaleString()}
                      {version.is_active && <span className="badge">Activa</span>}
                    </li>
                  ))}
                </ul>
              </details>
            ) : null}
          </section>

          <PropertiesPanel
            selected={selected}
            locations={locations}
            inventory={inventory}
            canViewCost={canViewCost}
            onChange={(element) => updateElement(element)}
            onDelete={() => setConfirmDelete(true)}
            onDuplicate={duplicate}
            onRotate={rotateSelection}
          />
        </div>

        <footer className="designer-footer">
          <span className="hint">Los cambios se guardan en el servidor al presionar «Guardar borrador»; la publicación requiere permiso explícito.</span>
          <div className="designer-footer-actions">
            <button type="button" className="button button-ghost" onClick={onClose}>Cerrar</button>
            <button type="button" className="button button-secondary" onClick={() => void save()} disabled={!editable || saving}>Guardar borrador</button>
            <button type="button" className="button button-primary" onClick={() => void publish()} disabled={!canPublish || saving || !draft}>Publicar versión</button>
          </div>
        </footer>
      </div>

      {wizardOpen && (
        <RackWizard
          x={wizardAnchor.current.x}
          y={wizardAnchor.current.y}
          canManageLocations={canManageLocations}
          onCancel={() => setWizardOpen(false)}
          onConfirm={(blueprint) => void createRack(blueprint)}
        />
      )}

      {confirmDelete && (
        <div className="modal-backdrop modal-backdrop-inner" role="presentation" onMouseDown={() => setConfirmDelete(false)}>
          <div className="modal-card confirm-card" role="alertdialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <h3>¿Eliminar {selectedIds.length} objeto(s)?</h3>
            <p>La acción se puede revertir con Deshacer antes de guardar.</p>
            <div className="modal-foot">
              <button type="button" className="button button-ghost" onClick={() => setConfirmDelete(false)}>Cancelar</button>
              <button type="button" className="button button-danger" onClick={deleteSelection}>Eliminar</button>
            </div>
          </div>
        </div>
      )}

      {importState && (
        <div className="modal-backdrop modal-backdrop-inner" role="presentation" onMouseDown={() => setImportState(null)}>
          <div className="modal-card confirm-card" role="dialog" aria-modal="true" onMouseDown={(event) => event.stopPropagation()}>
            <h3>Vista previa de importación</h3>
            <p>{importState.preview.label} · {importState.preview.element_count} elementos · {importState.preview.linked_location_count} referencias WMS · {importState.preview.width} × {importState.preview.height}</p>
            <p className="hint">{importState.preview.warning}</p>
            <form onSubmit={(event: FormEvent) => { event.preventDefault(); void applyImport(); }} className="modal-foot">
              <button type="button" className="button button-ghost" onClick={() => setImportState(null)}>Cancelar</button>
              <button type="submit" className="button button-primary" disabled={!editable}>Aplicar al borrador</button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
