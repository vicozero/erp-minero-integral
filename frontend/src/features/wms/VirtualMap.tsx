import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { api, ApiError } from '../../api/client';
import type {
  Catalogs,
  LocationMap,
  LocationMapVersion,
  LocationQr,
} from '../../api/types';
import { Icon } from '../../components/Icon';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  LoadingState,
  Panel,
  StatusBadge,
  SuccessMessage,
} from '../../components/ui';

type WarehouseOption = Catalogs['warehouses'][number];

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo completar la operación.';
}

function percent(value: string | null, total: string): number {
  const part = Number(value);
  const whole = Number(total);
  if (!Number.isFinite(part) || !Number.isFinite(whole) || whole <= 0) return 0;
  return Math.min(100, Math.max(0, (part / whole) * 100));
}

export interface VirtualMapProps {
  warehouses: WarehouseOption[];
  warehouseId: string;
  onWarehouseChange: (warehouseId: string) => void;
  canManage: boolean;
  selectedId: string | null;
  onSelectLocation: (locationId: string) => void;
}

export function VirtualMap({
  warehouses,
  warehouseId,
  onWarehouseChange,
  canManage,
  selectedId,
  onSelectLocation,
}: VirtualMapProps) {
  const [map, setMap] = useState<LocationMap | null>(null);
  const [versions, setVersions] = useState<LocationMapVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [metadata, setMetadata] = useState({ label: 'Referencial · no es plano exacto', width: '1000', height: '600', notes: '' });
  const [coordinates, setCoordinates] = useState({ x: '', y: '' });
  const [qr, setQr] = useState<LocationQr | null>(null);

  const load = useCallback(async (id: string) => {
    if (!id) {
      setMap(null);
      setVersions([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [detail, history] = await Promise.all([
        api.wmsLocationMap(id),
        api.wmsLocationMapVersions(id),
      ]);
      setMap(detail);
      setVersions(history);
      setMetadata({
        label: detail.label,
        width: detail.width,
        height: detail.height,
        notes: detail.notes ?? '',
      });
    } catch (exc) {
      setError(message(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(warehouseId);
  }, [load, warehouseId]);

  useEffect(() => {
    if (!selectedId) {
      setQr(null);
      return;
    }
    const node = map?.nodes.find((item) => item.id === selectedId);
    if (node?.coord_x && node?.coord_y) {
      setCoordinates({ x: node.coord_x, y: node.coord_y });
    } else {
      setCoordinates({ x: '', y: '' });
    }
    let active = true;
    api.locationQr(selectedId)
      .then((result) => { if (active) setQr(result); })
      .catch(() => { if (active) setQr(null); });
    return () => { active = false; };
  }, [map, selectedId]);

  async function saveCoordinates(event: FormEvent) {
    event.preventDefault();
    if (!selectedId || !coordinates.x || !coordinates.y) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api.updateLocationCoordinates(selectedId, coordinates.x, coordinates.y);
      setNotice('Coordenadas guardadas. El plano se actualizó desde la ubicación.');
      await load(warehouseId);
    } catch (exc) {
      setError(message(exc));
    } finally {
      setSaving(false);
    }
  }

  async function saveVersion(event: FormEvent) {
    event.preventDefault();
    if (!warehouseId) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api.updateLocationMap(warehouseId, {
        label: metadata.label,
        width: metadata.width,
        height: metadata.height,
        notes: metadata.notes || null,
      });
      setNotice('Se creó una nueva versión referencial del plano.');
      await load(warehouseId);
    } catch (exc) {
      setError(message(exc));
    } finally {
      setSaving(false);
    }
  }

  async function uploadBackground(file: File | undefined) {
    if (!warehouseId || !file) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      await api.uploadLocationMapBackground(warehouseId, {
        label: metadata.label,
        width: metadata.width,
        height: metadata.height,
        notes: metadata.notes || null,
      }, file);
      setNotice('Fondo cargado como referencia visual; no se presenta como plano exacto.');
      await load(warehouseId);
    } catch (exc) {
      setError(message(exc));
    } finally {
      setSaving(false);
    }
  }

  const selectedNode = map?.nodes.find((item) => item.id === selectedId) ?? null;
  const drawnNodes = map?.nodes.filter((item) => item.coord_x !== null && item.coord_y !== null) ?? [];
  const pendingNodes = map?.nodes.filter((item) => item.coord_x === null || item.coord_y === null) ?? [];

  return (
    <>
      <Panel
        title="Plano 2D del almacén"
        subtitle="Las posiciones se proyectan desde mdm.storage_location; el fondo es sólo una guía visual"
        icon="warehouse"
      >
        <div className="filter-bar">
          <label>
            Almacén del plano
            <select
              value={warehouseId}
              onChange={(event) => onWarehouseChange(event.target.value)}
              aria-label="Almacén del plano 2D"
            >
              <option value="">Seleccione…</option>
              {warehouses.map((warehouse) => (
                <option value={warehouse.id} key={warehouse.id}>{warehouse.name ?? warehouse.code}</option>
              ))}
            </select>
          </label>
          {map && (
            <span className="badge badge-partially_approved" aria-label={`Versión ${map.map_version} del plano`}>
              Versión {map.map_version}
            </span>
          )}
        </div>

        <p className="map-disclaimer" role="note">
          <Icon name="alert" size={14} /> {map?.label ?? 'Referencial · no es plano exacto'}.
          Las coordenadas no representan existencias y no sustituyen la verificación física.
        </p>

        <ErrorMessage message={error} />
        <SuccessMessage message={notice} />

        {loading ? (
          <LoadingState rows={4} />
        ) : !map ? (
          <EmptyState text="Seleccione un almacén para ver su plano referencial." />
        ) : (
          <div className="virtual-map-layout">
            <div className="warehouse-map" style={{ aspectRatio: `${map.width} / ${map.height}` }}>
              {map.background_url && (
                <img className="warehouse-map-background" src={map.background_url} alt="Fondo referencial del almacén" />
              )}
              <div className="warehouse-map-grid" aria-hidden="true" />
              {drawnNodes.map((node) => (
                <button
                  key={node.id}
                  type="button"
                  className={`map-node map-node-${node.location_type.toLowerCase()} ${selectedId === node.id ? 'map-node-selected' : ''}`}
                  style={{
                    left: `${percent(node.coord_x, map.width)}%`,
                    top: `${percent(node.coord_y, map.height)}%`,
                  }}
                  title={node.hierarchy_path}
                  aria-label={`Ubicación ${node.code} en el plano`}
                  onClick={() => onSelectLocation(node.id)}
                >
                  <span>{node.code}</span>
                  <small>{formatNumber(node.occupied_qty)}</small>
                </button>
              ))}
            </div>

            <aside className="map-sidebar" aria-label="Panel lateral de ubicación">
              {!selectedNode ? (
                <EmptyState text="Seleccione un punto del plano para ver su ficha." />
              ) : (
                <>
                  <h3>{selectedNode.code}</h3>
                  <p className="hint map-breadcrumb">{selectedNode.hierarchy_path}</p>
                  <p>
                    <StatusBadge status={selectedNode.status} />{' '}
                    <small>{selectedNode.item_count} artículos · {formatNumber(selectedNode.occupied_qty)} ocupados</small>
                  </p>
                  <form onSubmit={saveCoordinates} className="map-coordinate-form">
                    <label>
                      Coordenada X
                      <input
                        type="number"
                        step="0.0001"
                        min="0"
                        value={coordinates.x}
                        onChange={(event) => setCoordinates({ ...coordinates, x: event.target.value })}
                        disabled={!canManage}
                        aria-label="Coordenada X de la ubicación"
                      />
                    </label>
                    <label>
                      Coordenada Y
                      <input
                        type="number"
                        step="0.0001"
                        min="0"
                        value={coordinates.y}
                        onChange={(event) => setCoordinates({ ...coordinates, y: event.target.value })}
                        disabled={!canManage}
                        aria-label="Coordenada Y de la ubicación"
                      />
                    </label>
                    {canManage && (
                      <button className="button button-secondary button-small" type="submit" disabled={saving}>
                        Guardar coordenadas
                      </button>
                    )}
                  </form>
                  {qr && (
                    <div className="map-qr">
                      <p className="hint">Etiqueta QR opaca</p>
                      <code>{qr.qr_token}</code>
                      <a href={qr.svg_url} target="_blank" rel="noreferrer">Ver código QR</a>
                    </div>
                  )}
                </>
              )}
            </aside>
          </div>
        )}

        {pendingNodes.length > 0 && (
          <p className="hint">
            Sin coordenadas en el plano: {pendingNodes.map((node) => node.code).join(', ')}
          </p>
        )}

        {canManage && (
          <div className="map-admin">
            <form className="search-toolbar" onSubmit={saveVersion}>
              <label>
                Etiqueta del plano
                <input
                  value={metadata.label}
                  onChange={(event) => setMetadata({ ...metadata, label: event.target.value })}
                  aria-label="Etiqueta del plano"
                />
              </label>
              <label>
                Ancho
                <input
                  type="number"
                  min="1"
                  step="0.0001"
                  value={metadata.width}
                  onChange={(event) => setMetadata({ ...metadata, width: event.target.value })}
                  aria-label="Ancho del plano"
                />
              </label>
              <label>
                Alto
                <input
                  type="number"
                  min="1"
                  step="0.0001"
                  value={metadata.height}
                  onChange={(event) => setMetadata({ ...metadata, height: event.target.value })}
                  aria-label="Alto del plano"
                />
              </label>
              <button className="button button-secondary align-end" type="submit" disabled={saving}>
                Guardar nueva versión
              </button>
            </form>
            <label className="map-background-upload">
              Fondo referencial (PNG, JPG o WEBP · máximo 5 MB)
              <input
                type="file"
                accept=".png,.jpg,.jpeg,.webp"
                disabled={saving || !warehouseId}
                onChange={(event) => void uploadBackground(event.target.files?.[0])}
                aria-label="Fondo referencial del plano"
              />
            </label>
          </div>
        )}

        {versions.length > 0 && (
          <details className="map-versions">
            <summary>Historial de versiones ({versions.length})</summary>
            <ul>
              {versions.map((version) => (
                <li key={version.id}>
                  v{version.map_version} · {version.label}
                  {version.background_name ? ` · ${version.background_name}` : ' · sin fondo'}
                  {version.is_active ? ' · activa' : ''}
                </li>
              ))}
            </ul>
          </details>
        )}
      </Panel>
    </>
  );
}
