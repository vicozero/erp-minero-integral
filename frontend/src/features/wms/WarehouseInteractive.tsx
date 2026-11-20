import { lazy, Suspense, useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { api, ApiError } from '../../api/client';
import type {
  Catalogs,
  ItemFamily,
  LocationInventory,
  LocationMap,
  MaterialSearchResult,
  WarehouseDashboard,
} from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { can, PERM } from '../../auth/permissions';
import { Icon } from '../../components/Icon';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  LoadingState,
  PageHeader,
  StatusBadge,
} from '../../components/ui';
import { InteractiveMap2D } from './InteractiveMap2D';
import { SceneErrorBoundary } from './SceneErrorBoundary';
import { VirtualMap } from './VirtualMap';
import { Designer } from './designer/Designer';
import { webglAvailable } from './webgl';
import { DEFAULT_GEOMETRY, type GeometrySettings } from './warehouse3dConfig';

const Warehouse3D = lazy(() => import('./Warehouse3D'));

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo completar la operación.';
}

type ViewMode = '2d' | '3d';

function Kpi({ label, value, detail, tone }: { label: string; value: string | number; detail?: string; tone?: string }) {
  return (
    <div className={`kpi-card ${tone ? `kpi-${tone}` : ''}`}>
      <small>{label}</small>
      <strong>{value}</strong>
      {detail && <span>{detail}</span>}
    </div>
  );
}

export function WarehouseInteractive() {
  const { user } = useAuth();
  const canManageMap = can(user, ...PERM.MANAGE_MAPS);
  const canViewMaps = can(user, ...PERM.VIEW_MAPS);
  const canViewStock = can(user, ...PERM.VIEW_STOCK_COST);
  const canOpenDesigner = canViewMaps || can(user, ...PERM.VIEW_PLANS);
  const canEditPlan = can(user, ...PERM.EDIT_PLANS);
  const canPublishPlan = can(user, ...PERM.PUBLISH_PLANS);

  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [families, setFamilies] = useState<ItemFamily[]>([]);
  const [warehouseId, setWarehouseId] = useState('');
  const [zone, setZone] = useState('');
  const [familyId, setFamilyId] = useState('');
  const [view, setView] = useState<ViewMode>('2d');
  const [map, setMap] = useState<LocationMap | null>(null);
  const [dashboard, setDashboard] = useState<WarehouseDashboard | null>(null);
  const [inventory, setInventory] = useState<LocationInventory | null>(null);
  const [searchResult, setSearchResult] = useState<MaterialSearchResult | null>(null);
  const [query, setQuery] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [panelCollapsed, setPanelCollapsed] = useState(false);
  const [panelWidth, setPanelWidth] = useState(360);
  const [detailed, setDetailed] = useState(true);
  const [resetToken, setResetToken] = useState(0);
  const [geometry, setGeometry] = useState<GeometrySettings>(DEFAULT_GEOMETRY);
  const [editorOpen, setEditorOpen] = useState(false);
  const [designerOpen, setDesignerOpen] = useState(false);
  const [webgl] = useState(() => webglAvailable());

  const warehouses = useMemo(() => catalogs?.warehouses ?? [], [catalogs]);
  const zones = useMemo(() => {
    const values = new Set<string>();
    (map?.nodes ?? []).forEach((node) => {
      if (node.zone) values.add(node.zone);
    });
    return Array.from(values).sort();
  }, [map]);
  const highlightIds = useMemo(() => searchResult?.location_ids ?? [], [searchResult]);

  useEffect(() => {
    let active = true;
    api
      .catalogs()
      .then((result) => {
        if (!active) return;
        setCatalogs(result);
        setWarehouseId((current) => current || result.warehouses[0]?.id || '');
      })
      .catch((exc) => setError(message(exc)));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    api
      .wmsFamilies()
      .then((result) => {
        if (active) setFamilies(result);
      })
      .catch(() => {
        // El filtro de familia queda vacío; el backend mantiene el alcance.
      });
    return () => {
      active = false;
    };
  }, []);

  const loadWorkspace = useCallback(async (id: string) => {
    if (!id) {
      setMap(null);
      setDashboard(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [nextMap, nextDashboard] = await Promise.all([
        api.wmsLocationMap(id),
        api.wmsDashboard({
          warehouse_id: id,
          zone: zone || undefined,
          family_id: familyId || undefined,
        }),
      ]);
      setMap(nextMap);
      setDashboard(nextDashboard);
    } catch (exc) {
      setError(message(exc));
    } finally {
      setLoading(false);
    }
  }, [familyId, zone]);

  useEffect(() => {
    void loadWorkspace(warehouseId);
  }, [loadWorkspace, warehouseId]);

  const selectLocation = useCallback(async (locationId: string) => {
    setSelectedId(locationId);
    setLoadingDetail(true);
    setNotice(null);
    try {
      setInventory(await api.wmsLocationInventory(locationId));
    } catch (exc) {
      setError(message(exc));
      setInventory(null);
    } finally {
      setLoadingDetail(false);
    }
  }, []);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    if (query.trim().length < 2) {
      setNotice('Escriba al menos dos caracteres para buscar refacciones.');
      return;
    }
    setSearching(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.wmsMaterialSearch(query.trim(), {
        warehouse_id: warehouseId || undefined,
        zone: zone || undefined,
        family_id: familyId || undefined,
      });
      setSearchResult(result);
      if (result.location_ids.length === 0) {
        setNotice('La búsqueda no devolvió ubicaciones con existencias en este almacén.');
      }
    } catch (exc) {
      setError(message(exc));
    } finally {
      setSearching(false);
    }
  }

  function focusMaterial(locationId: string) {
    void selectLocation(locationId);
  }

  const totals = dashboard?.totals;
  const alerts = dashboard?.alerts;
  const hasMapNodes = (map?.nodes ?? []).some((node) => node.coord_x !== null && node.coord_y !== null);

  return (
    <div className="warehouse-interactive">
      <PageHeader
        title="Almacén virtual 2D / 3D"
        subtitle="Ubicaciones y existencias reales del WMS · plano referencial versionado"
        actions={
          <>
            <button
              type="button"
              className="button button-primary"
              onClick={() => setDesignerOpen(true)}
              disabled={!canOpenDesigner || !warehouseId}
              data-testid="editar-plano"
            >
              Editar plano
            </button>
            <span className="badge badge-partially_approved" aria-label="Inventario operativo">
              Inventario operativo
            </span>
          </>
        }
      />

      <div className="wi-toolbar" role="toolbar" aria-label="Barra de herramientas del almacén virtual">
        <label>
          Almacén
          <select
            value={warehouseId}
            onChange={(event) => {
              setWarehouseId(event.target.value);
              setSelectedId(null);
              setInventory(null);
              setSearchResult(null);
            }}
            aria-label="Seleccionar almacén"
          >
            <option value="">Seleccione…</option>
            {warehouses.map((warehouse) => (
              <option key={warehouse.id} value={warehouse.id}>
                {warehouse.name ?? warehouse.code}
              </option>
            ))}
          </select>
        </label>
        <label>
          Zona
          <select value={zone} onChange={(event) => setZone(event.target.value)} aria-label="Filtrar por zona">
            <option value="">Todas</option>
            {zones.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Familia
          <select value={familyId} onChange={(event) => setFamilyId(event.target.value)} aria-label="Filtrar por familia">
            <option value="">Todas</option>
            {families.map((family) => (
              <option key={family.id} value={family.id}>{family.name}</option>
            ))}
          </select>
        </label>
        <div className="view-switch" role="group" aria-label="Modo de visualización">
          <button
            type="button"
            className={view === '2d' ? 'button button-primary button-small' : 'button button-ghost button-small'}
            onClick={() => setView('2d')}
          >
            Vista 2D
          </button>
          <button
            type="button"
            className={view === '3d' ? 'button button-primary button-small' : 'button button-ghost button-small'}
            onClick={() => setView('3d')}
          >
            Vista 3D
          </button>
        </div>
        <form className="wi-search" onSubmit={handleSearch} role="search">
          <Icon name="search" size={16} />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar refacción, código o número de parte…"
            aria-label="Buscar refacciones"
          />
          <button type="submit" className="button button-secondary button-small" disabled={searching}>
            {searching ? 'Buscando…' : 'Localizar'}
          </button>
        </form>
      </div>

      <ErrorMessage message={error} />
      {notice && (
        <p className="hint" role="status">{notice}</p>
      )}

      <div className="kpi-grid" aria-label="Indicadores del almacén">
        <Kpi label="Ubicaciones totales" value={totals?.location_count ?? '—'} />
        <Kpi label="Ocupadas" value={totals?.occupied ?? '—'} tone="success" />
        <Kpi label="Vacías" value={totals?.empty ?? '—'} />
        <Kpi label="Bloqueadas" value={totals?.blocked ?? '—'} tone="warning" />
        {totals && totals.capacity_defined_count > 0 && (
          <Kpi
            label="Capacidad utilizada"
            value={totals.capacity_used_pct === null ? '—' : `${formatNumber(totals.capacity_used_pct)} %`}
            detail={`${formatNumber(totals.occupied_in_capacity_qty)} / ${formatNumber(totals.capacity_qty)} · ${totals.capacity_defined_count} ubicaciones con capacidad`}
          />
        )}
        <Kpi label="Bajo mínimo" value={alerts?.below_minimum.length ?? '—'} tone="warning" />
        <Kpi label="Sin ubicación" value={alerts?.unlocated.length ?? '—'} tone="warning" />
      </div>

      <div className="wi-layout" style={{ gridTemplateColumns: panelCollapsed ? '1fr 44px' : `1fr ${panelWidth}px` }}>
        <section className="wi-canvas" aria-label="Área de visualización">
          {!canViewMaps ? (
            <EmptyState text="Su perfil no tiene permiso para consultar planos del almacén." />
          ) : loading ? (
            <LoadingState rows={6} label="Cargando plano y existencias del almacén…" />
          ) : !map ? (
            <EmptyState text="Seleccione un almacén para visualizar su distribución." />
          ) : !hasMapNodes ? (
            <EmptyState text="Este almacén aún no tiene ubicaciones con coordenadas referenciales." />
          ) : view === '2d' ? (
            <InteractiveMap2D
              nodes={map.nodes}
              width={map.width}
              height={map.height}
              label={map.label}
              backgroundUrl={map.background_url}
              selectedId={selectedId}
              highlightIds={highlightIds}
              onSelect={(id) => void selectLocation(id)}
            />
          ) : !webgl ? (
            <div className="webgl-fallback" role="alert">
              <Icon name="alert" size={20} />
              <h3>WebGL no está disponible</h3>
              <p>La vista 3D requiere aceleración gráfica. La vista 2D sigue siendo completamente funcional.</p>
              <button type="button" className="button button-primary" onClick={() => setView('2d')}>
                Volver a la vista 2D
              </button>
            </div>
          ) : (
            <>
              <div className="scene-toolbar" role="toolbar" aria-label="Controles de la vista 3D">
                <label className="checkbox-line">
                  <input type="checkbox" checked={detailed} onChange={(event) => setDetailed(event.target.checked)} />
                  Vista detallada
                </label>
                <button type="button" className="button button-ghost button-small" onClick={() => setResetToken((value) => value + 1)}>
                  Restablecer cámara
                </button>
                <label title="Ancho referencial del rack">
                  Ancho rack
                  <input
                    type="range" min="1" max="6" step="0.1" value={geometry.rackWidth}
                    onChange={(event) => setGeometry({ ...geometry, rackWidth: Number(event.target.value) })}
                  />
                </label>
                <label title="Profundidad referencial del rack">
                  Profundidad
                  <input
                    type="range" min="1" max="6" step="0.1" value={geometry.rackDepth}
                    onChange={(event) => setGeometry({ ...geometry, rackDepth: Number(event.target.value) })}
                  />
                </label>
                <label title="Altura referencial por nivel">
                  Altura nivel
                  <input
                    type="range" min="0.5" max="2.5" step="0.1" value={geometry.levelHeight}
                    onChange={(event) => setGeometry({ ...geometry, levelHeight: Number(event.target.value) })}
                  />
                </label>
                <span className="scene-note">Geometría referencial, no medición física</span>
              </div>
              <SceneErrorBoundary onFallback={() => setView('2d')}>
                <Suspense fallback={<LoadingState rows={5} label="Preparando escena 3D…" />}>
                  <Warehouse3D
                    nodes={map.nodes}
                    width={map.width}
                    height={map.height}
                    selectedId={selectedId}
                    highlightIds={highlightIds}
                    detailed={detailed}
                    resetToken={resetToken}
                    geometry={geometry}
                    onSelect={(id) => void selectLocation(id)}
                  />
                </Suspense>
              </SceneErrorBoundary>
            </>
          )}
        </section>

        <aside className={`wi-panel ${panelCollapsed ? 'is-collapsed' : ''}`} aria-label="Panel lateral de información">
          <div className="wi-panel-head">
            <button
              type="button"
              className="icon-button"
              onClick={() => setPanelCollapsed((value) => !value)}
              aria-label={panelCollapsed ? 'Expandir panel' : 'Contraer panel'}
              aria-expanded={!panelCollapsed}
            >
              <Icon name="menu" size={16} />
            </button>
            {!panelCollapsed && <strong>Información</strong>}
          </div>
          {!panelCollapsed && (
            <div className="wi-panel-body">
              <label className="panel-resize">
                Ancho del panel
                <input
                  type="range" min="280" max="560" step="10" value={panelWidth}
                  onChange={(event) => setPanelWidth(Number(event.target.value))}
                  aria-label="Redimensionar panel lateral"
                />
              </label>

              <section className="wi-section">
                <h3>Ubicación seleccionada</h3>
                {loadingDetail ? (
                  <LoadingState rows={3} label="Consultando inventario real…" />
                ) : !inventory ? (
                  <EmptyState text="Seleccione una ubicación en el plano 2D o en la escena 3D." />
                ) : (
                  <div className="inventory-card" data-testid="panel-inventario">
                    <h4>{inventory.code}</h4>
                    <p className="hint">{inventory.hierarchy_path}</p>
                    <p><StatusBadge status={inventory.status} /> <small>{inventory.location_type}</small></p>
                    <dl className="detail-grid">
                      <div><dt>Física</dt><dd>{formatNumber(inventory.occupied_qty)}</dd></div>
                      <div><dt>Disponible</dt><dd>{formatNumber(inventory.items.reduce((sum, row) => sum + Number(row.available_qty), 0))}</dd></div>
                      <div><dt>Reservada</dt><dd>{formatNumber(inventory.items.reduce((sum, row) => sum + Number(row.reserved_qty), 0))}</dd></div>
                      <div><dt>Capacidad</dt><dd>{formatNumber(inventory.capacity_qty)}</dd></div>
                    </dl>
                    {inventory.is_empty ? (
                      <EmptyState text="Esta ubicación no tiene existencias registradas." />
                    ) : (
                      <ul className="inventory-list">
                        {inventory.items.map((item) => (
                          <li key={item.item_id} data-testid="item-inventario">
                            <strong>{item.code}</strong> · {item.description}
                            <div className="hint">
                              {item.manufacturer_part_no ? `Parte ${item.manufacturer_part_no} · ` : ''}
                              {item.internal_code ? `Interno ${item.internal_code} · ` : ''}
                              {item.lot_number ? `Lote ${item.lot_number} · ` : ''}
                              {item.uom_code}
                            </div>
                            <div>
                              Física {formatNumber(item.on_hand_qty)} · Disp. {formatNumber(item.available_qty)} · Res. {formatNumber(item.reserved_qty)}
                              {inventory.can_view_cost && item.unit_cost !== null && ` · Costo ${formatNumber(item.unit_cost)}`}
                            </div>
                            {item.last_movement && (
                              <div className="hint">
                                Último movimiento: {item.last_movement.movement_no} · {item.last_movement.movement_type} · {formatNumber(item.last_movement.quantity)}
                              </div>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                    {inventory.restrictions.length > 0 && (
                      <p className="hint">
                        Restricciones: {inventory.restrictions.map((row) => row.item_family_name ?? row.item_code ?? 'Regla').join(', ')}
                      </p>
                    )}
                    {!inventory.can_view_cost && (
                      <p className="hint">El costo se omite: su perfil no tiene autorización para consultarlo.</p>
                    )}
                  </div>
                )}
              </section>

              <section className="wi-section">
                <h3>Búsqueda de refacciones</h3>
                {!searchResult ? (
                  <EmptyState text="Busque por descripción, código o número de parte para resaltar ubicaciones." />
                ) : searchResult.materials.length === 0 ? (
                  <EmptyState text={`Sin resultados para “${searchResult.query}”.`} />
                ) : (
                  <ul className="search-results">
                    {searchResult.materials.map((material) => (
                      <li key={material.item_id}>
                        <strong>{material.code}</strong> · {material.description}
                        <div className="hint">
                          {material.manufacturer_part_no ? `Parte ${material.manufacturer_part_no} · ` : ''}
                          {material.uom_code} · {material.location_count} ubicación(es)
                        </div>
                        {material.locations.map((location) => (
                          <button
                            key={location.location_id}
                            type="button"
                            className="link-button"
                            onClick={() => focusMaterial(location.location_id)}
                          >
                            {location.location_code} · {formatNumber(location.available_qty)} disponibles
                          </button>
                        ))}
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              {alerts && (
                <section className="wi-section">
                  <h3>Alertas de inventario</h3>
                  <p className="hint">Bajo mínimo ({alerts.below_minimum.length}) · Críticos ({alerts.critical.length}) · Sin ubicación ({alerts.unlocated.length})</p>
                  {alerts.below_minimum.slice(0, 5).map((row) => (
                    <p key={row.item_id} className="alert-line">
                      <strong>{row.code}</strong> · {formatNumber(row.on_hand_qty)} / mín. {formatNumber(row.reorder_point)} {row.uom_code}
                    </p>
                  ))}
                  {alerts.unlocated.slice(0, 5).map((row) => (
                    <p key={row.item_id} className="alert-line">
                      <strong>{row.code}</strong> · {formatNumber(row.on_hand_qty)} {row.uom_code} sin ubicación
                    </p>
                  ))}
                </section>
              )}

              <details
                className="wi-map-editor"
                open={editorOpen}
                onToggle={(event) => setEditorOpen((event.currentTarget as HTMLDetailsElement).open)}
              >
                <summary>Editor del plano referencial y versiones</summary>
                {editorOpen && (
                  <VirtualMap
                    warehouses={warehouses}
                    warehouseId={warehouseId}
                    onWarehouseChange={setWarehouseId}
                    canManage={canManageMap}
                    selectedId={selectedId ?? ''}
                    onSelectLocation={(id) => void selectLocation(id)}
                  />
                )}
              </details>

              {!canViewStock && (
                <p className="hint">Costos y kardex se muestran sólo a perfiles autorizados.</p>
              )}
            </div>
          )}
        </aside>
      </div>

      {designerOpen && (
        <Designer
          warehouseId={warehouseId}
          warehouseLabel={
            warehouses.find((warehouse) => warehouse.id === warehouseId)?.name
            ?? warehouses.find((warehouse) => warehouse.id === warehouseId)?.code
            ?? warehouseId
          }
          canEdit={canEditPlan}
          canPublish={canPublishPlan}
          canManageLocations={canManageMap}
          canViewCost={canViewStock}
          onClose={() => setDesignerOpen(false)}
          onSaved={() => void loadWorkspace(warehouseId)}
        />
      )}
    </div>
  );
}
