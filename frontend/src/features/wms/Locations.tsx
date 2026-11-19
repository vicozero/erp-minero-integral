import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react';
import { api, ApiError } from '../../api/client';
import type { Catalogs, WmsLocation, WmsLocationDetail } from '../../api/types';
import { useAuth } from '../../auth/AuthContext';
import { can, PERM } from '../../auth/permissions';
import { Icon } from '../../components/Icon';
import { VirtualMap } from './VirtualMap';
import {
  EmptyState,
  ErrorMessage,
  formatNumber,
  LoadingState,
  PageHeader,
  Panel,
  ProgressBar,
  StatusBadge,
  SuccessMessage,
} from '../../components/ui';

const LOCATION_TYPES = ['RECEIPT', 'STANDARD', 'QUARANTINE', 'DISPATCH', 'TRANSIT', 'SCRAP'] as const;
const TYPE_LABELS: Record<string, string> = {
  RECEIPT: 'Recepción',
  STANDARD: 'Almacenamiento',
  QUARANTINE: 'Cuarentena',
  DISPATCH: 'Despacho',
  TRANSIT: 'Tránsito',
  SCRAP: 'Desecho',
};

function message(error: unknown): string {
  return error instanceof ApiError ? error.message : 'No se pudo completar la operación.';
}

export function Locations() {
  const { user } = useAuth();
  const canManage = can(user, ...PERM.MANAGE_LOCATIONS);
  const canManageMap = can(user, ...PERM.MANAGE_MAPS);

  const [catalogs, setCatalogs] = useState<Catalogs | null>(null);
  const [warehouseId, setWarehouseId] = useState('');
  const [mapWarehouseId, setMapWarehouseId] = useState('');
  const [locationType, setLocationType] = useState('');
  const [status, setStatus] = useState('');
  const [query, setQuery] = useState('');
  const [locations, setLocations] = useState<WmsLocation[]>([]);
  const [detail, setDetail] = useState<WmsLocationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState({
    warehouse_id: '',
    code: '',
    zone: '',
    aisle: '',
    rack: '',
    level: '',
    position: '',
    location_type: 'STANDARD' as (typeof LOCATION_TYPES)[number],
    capacity_qty: '1000',
    status: 'ACTIVE' as 'ACTIVE' | 'BLOCKED' | 'INACTIVE',
    is_pickable: true,
    is_receivable: true,
  });

  const warehouses = useMemo(() => catalogs?.warehouses ?? [], [catalogs]);

  const load = useCallback(async (filters: { warehouse_id?: string; location_type?: string; status?: string; query?: string }) => {
    setLoading(true);
    setError(null);
    try {
      setLocations(await api.wmsLocations(filters));
    } catch (exc) {
      setError(message(exc));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    api.catalogs().then((result) => {
      if (!active) return;
      setCatalogs(result);
      const first = result.warehouses[0]?.id ?? '';
      setForm((current) => ({ ...current, warehouse_id: current.warehouse_id || first }));
      setMapWarehouseId((current) => current || first);
    }).catch(() => {
      // El filtro de almacén queda vacío; el backend aplica su alcance.
    });
    void load({});
    return () => { active = false; };
  }, [load]);

  async function handleSearch(event: FormEvent) {
    event.preventDefault();
    await load({
      warehouse_id: warehouseId || undefined,
      location_type: locationType || undefined,
      status: status || undefined,
      query: query.trim() || undefined,
    });
  }

  async function openDetail(id: string) {
    setLoadingDetail(true);
    setError(null);
    try {
      setDetail(await api.wmsLocationDetail(id));
    } catch (exc) {
      setError(message(exc));
    } finally {
      setLoadingDetail(false);
    }
  }

  async function handleCreate(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.createLocation({
        warehouse_id: form.warehouse_id,
        code: form.code.trim(),
        zone: form.zone.trim() || null,
        aisle: form.aisle.trim() || null,
        rack: form.rack.trim() || null,
        level: form.level.trim() || null,
        position: form.position.trim() || null,
        location_type: form.location_type,
        capacity_qty: form.capacity_qty,
        status: form.status,
        is_pickable: form.is_pickable,
        is_receivable: form.is_receivable,
      });
      setNotice(`Ubicación ${created.code} creada con token ${created.qr_token}.`);
      setForm((current) => ({ ...current, code: '' }));
      await load({});
      await openDetail(created.id);
    } catch (exc) {
      setError(message(exc));
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Ubicaciones de almacén"
        subtitle="Estructura física, capacidad, ocupación y referencias de etiqueta WMS"
        actions={<span className="badge badge-active"><Icon name="location" size={13} /> Lote A · WMS</span>}
      />
      <div className="demo-ribbon" role="note">
        <Icon name="demo" size={15} />
        DEMOSTRACIÓN · Datos sintéticos aislados · Inventario operativo, no oficial
      </div>

      <ErrorMessage message={error} />
      <SuccessMessage message={notice} />

      <Panel title="Filtrar ubicaciones" icon="search">
        <form className="search-toolbar" onSubmit={handleSearch}>
          <label>
            Texto, zona o pasillo
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Ej. A-01 o R1"
              aria-label="Buscar ubicación"
            />
          </label>
          <label>
            Almacén
            <select value={warehouseId} onChange={(event) => setWarehouseId(event.target.value)} aria-label="Filtrar por almacén">
              <option value="">Todos</option>
              {warehouses.map((warehouse) => (
                <option value={warehouse.id} key={warehouse.id}>{warehouse.name ?? warehouse.code}</option>
              ))}
            </select>
          </label>
          <label>
            Tipo
            <select value={locationType} onChange={(event) => setLocationType(event.target.value)} aria-label="Filtrar por tipo de ubicación">
              <option value="">Todos</option>
              {LOCATION_TYPES.map((type) => <option value={type} key={type}>{TYPE_LABELS[type]}</option>)}
            </select>
          </label>
          <label>
            Estado
            <select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filtrar por estado">
              <option value="">Todos</option>
              <option value="ACTIVE">Activa</option>
              <option value="BLOCKED">Bloqueada</option>
              <option value="INACTIVE">Inactiva</option>
            </select>
          </label>
          <button type="submit" className="button button-primary align-end" disabled={loading}>
            <Icon name="search" size={14} /> Buscar
          </button>
        </form>
      </Panel>

      <VirtualMap
        warehouses={warehouses}
        warehouseId={mapWarehouseId}
        onWarehouseChange={setMapWarehouseId}
        canManage={canManageMap}
        selectedId={detail?.id ?? null}
        onSelectLocation={(id) => void openDetail(id)}
      />

      {canManage && (
        <Panel title="Nueva ubicación" icon="location" subtitle="El token QR opaco se genera automáticamente y se registra en auditoría">
          <form onSubmit={handleCreate}>
            <div className="search-toolbar">
              <label>
                Almacén
                <select
                  value={form.warehouse_id}
                  onChange={(event) => setForm({ ...form, warehouse_id: event.target.value })}
                  required
                  aria-label="Almacén de la nueva ubicación"
                >
                  <option value="">Seleccione…</option>
                  {warehouses.map((warehouse) => (
                    <option value={warehouse.id} key={warehouse.id}>{warehouse.name ?? warehouse.code}</option>
                  ))}
                </select>
              </label>
              <label>
                Código
                <input
                  value={form.code}
                  onChange={(event) => setForm({ ...form, code: event.target.value })}
                  placeholder="A-03-R2-1-04"
                  required
                  aria-label="Código de la nueva ubicación"
                />
              </label>
              <label>
                Zona
                <input value={form.zone} onChange={(event) => setForm({ ...form, zone: event.target.value })} aria-label="Zona" />
              </label>
              <label>
                Pasillo
                <input value={form.aisle} onChange={(event) => setForm({ ...form, aisle: event.target.value })} aria-label="Pasillo" />
              </label>
              <label>
                Estante
                <input value={form.rack} onChange={(event) => setForm({ ...form, rack: event.target.value })} aria-label="Estante" />
              </label>
              <label>
                Nivel
                <input value={form.level} onChange={(event) => setForm({ ...form, level: event.target.value })} aria-label="Nivel" />
              </label>
              <label>
                Posición
                <input value={form.position} onChange={(event) => setForm({ ...form, position: event.target.value })} aria-label="Posición" />
              </label>
              <label>
                Tipo
                <select
                  value={form.location_type}
                  onChange={(event) => setForm({ ...form, location_type: event.target.value as (typeof LOCATION_TYPES)[number] })}
                  aria-label="Tipo de la nueva ubicación"
                >
                  {LOCATION_TYPES.map((type) => <option value={type} key={type}>{TYPE_LABELS[type]}</option>)}
                </select>
              </label>
              <label>
                Capacidad
                <input
                  type="number"
                  min="0"
                  step="0.000001"
                  value={form.capacity_qty}
                  onChange={(event) => setForm({ ...form, capacity_qty: event.target.value })}
                  aria-label="Capacidad de la ubicación"
                />
              </label>
              <label>
                Estado
                <select
                  value={form.status}
                  onChange={(event) => setForm({ ...form, status: event.target.value as 'ACTIVE' | 'BLOCKED' | 'INACTIVE' })}
                  aria-label="Estado de la nueva ubicación"
                >
                  <option value="ACTIVE">Activa</option>
                  <option value="BLOCKED">Bloqueada</option>
                  <option value="INACTIVE">Inactiva</option>
                </select>
              </label>
            </div>
            <div className="form-actions">
              <label className="checkbox-line">
                <input
                  type="checkbox"
                  checked={form.is_pickable}
                  onChange={(event) => setForm({ ...form, is_pickable: event.target.checked })}
                  aria-label="Permitir surtido"
                />
                Permite surtido
              </label>
              <label className="checkbox-line">
                <input
                  type="checkbox"
                  checked={form.is_receivable}
                  onChange={(event) => setForm({ ...form, is_receivable: event.target.checked })}
                  aria-label="Permitir recepción"
                />
                Permite recepción
              </label>
              <button type="submit" className="button button-secondary" disabled={saving}>
                <Icon name="check" size={14} /> Crear ubicación
              </button>
            </div>
          </form>
        </Panel>
      )}

      <div className="panel-grid">
        <Panel title={`Ubicaciones (${locations.length})`} icon="warehouse" subtitle="La ocupación se calcula desde los saldos de inventario, no se captura manualmente">
          {loading ? (
            <LoadingState rows={5} />
          ) : locations.length === 0 ? (
            <EmptyState text="No hay ubicaciones que coincidan con los filtros." />
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>Código</th><th>Almacén</th><th>Tipo</th><th>Estado</th><th>Ocupación</th><th>Artículos</th></tr>
                </thead>
                <tbody>
                  {locations.map((location) => {
                    const capacity = Number(location.capacity_qty) || 0;
                    return (
                      <tr key={location.id}>
                        <td>
                          <button type="button" className="link-button" onClick={() => void openDetail(location.id)} aria-label={`Ver ficha de ${location.code}`}>
                            {location.code}
                          </button>
                          <small className="hint">{[location.zone, location.aisle, location.rack].filter(Boolean).join(' · ')}</small>
                        </td>
                        <td>{location.warehouse_code}</td>
                        <td>{TYPE_LABELS[location.location_type] ?? location.location_type}</td>
                        <td><StatusBadge status={location.status} /></td>
                        <td>
                          <ProgressBar
                            value={Number(location.occupied_qty)}
                            max={capacity}
                            tone={capacity > 0 && Number(location.occupied_qty) / capacity > 0.85 ? 'warning' : 'default'}
                            label={`${formatNumber(location.occupied_qty)} / ${formatNumber(location.capacity_qty)}`}
                          />
                        </td>
                        <td>{location.item_count}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel title="Ficha de ubicación" icon="location" subtitle="Restricciones, saldos asignados y referencia de etiqueta">
          {loadingDetail ? (
            <LoadingState rows={4} />
          ) : !detail ? (
            <EmptyState text="Seleccione una ubicación de la tabla para ver su ficha." />
          ) : (
            <div className="detail-stack">
              <div className="detail-header">
                <div>
                  <h3>{detail.code}</h3>
                  <p>{TYPE_LABELS[detail.location_type] ?? detail.location_type} · {detail.warehouse_code}</p>
                  <StatusBadge status={detail.status} />
                </div>
              </div>

              <div className="detail-grid">
                <div><span>Zona</span><strong>{detail.zone ?? '—'}</strong></div>
                <div><span>Pasillo</span><strong>{detail.aisle ?? '—'}</strong></div>
                <div><span>Estante</span><strong>{detail.rack ?? '—'}</strong></div>
                <div><span>Nivel</span><strong>{detail.level ?? '—'}</strong></div>
                <div><span>Posición</span><strong>{detail.position ?? '—'}</strong></div>
                <div><span>Capacidad</span><strong>{formatNumber(detail.capacity_qty)}</strong></div>
                <div><span>Ocupación</span><strong>{formatNumber(detail.occupied_qty)}</strong></div>
                <div><span>Surtido / recepción</span><strong>{detail.is_pickable ? 'Sí' : 'No'} / {detail.is_receivable ? 'Sí' : 'No'}</strong></div>
              </div>

              <div>
                <span className="hint">Referencia de etiqueta WMS</span>
                <div className="qr-token">{detail.qr_token}</div>
                <span className="hint">Token legible para impresión. La generación gráfica y lectura de QR queda pendiente de la Fase 5.</span>
              </div>

              <h3>Restricciones</h3>
              {detail.restrictions.length === 0 ? (
                <EmptyState text="Sin restricciones por familia o artículo." />
              ) : (
                <div className="chip-row">
                  {detail.restrictions.map((restriction, index) => (
                    <span className="chip" key={`${restriction.item_family_id ?? restriction.item_id ?? 'repo'}-${index}`}>
                      Máximo {formatNumber(restriction.max_qty)} · mezcla lotes {restriction.allows_lot_mix ? 'sí' : 'no'} · mezcla series {restriction.allows_serial_mix ? 'sí' : 'no'}
                    </span>
                  ))}
                </div>
              )}

              <h3>Saldos en esta ubicación</h3>
              {detail.items.length === 0 ? (
                <EmptyState text="No hay existencias asignadas a esta ubicación." />
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead><tr><th>Lote</th><th>Ubicación</th><th>Existencia</th><th>Reservado</th><th>Disponible</th></tr></thead>
                    <tbody>
                      {detail.items.map((item, index) => (
                        <tr key={`${item.location_id}-${item.lot_number ?? 'sin-lote'}-${index}`}>
                          <td>{item.lot_number ?? '—'}</td>
                          <td>{item.location_code}</td>
                          <td>{formatNumber(item.on_hand_qty)}</td>
                          <td>{formatNumber(item.reserved_qty)}</td>
                          <td>{formatNumber(item.available_qty)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </Panel>
      </div>
    </>
  );
}
